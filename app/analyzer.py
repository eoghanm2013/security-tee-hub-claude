"""
Pre-analysis engine for TEE Hub.

Automatically analyzes assets in an investigation folder and generates
a pre-analysis.md report. Handles:
  - Datadog agent flares (zip files with known structure)
  - Images/screenshots (via Gemini or Claude vision)
  - Log files (regex extraction + optional LLM summary)
  - CSV files (row/column stats)
"""

import os
import re
import csv
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from io import StringIO

ROOT = Path(__file__).resolve().parent.parent
INVESTIGATIONS_DIR = ROOT / "investigations"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
LOG_EXTENSIONS = {".log", ".txt", ".out"}
CSV_EXTENSIONS = {".csv", ".tsv"}

# Known paths inside a Datadog agent flare
FLARE_CONFIG_PATHS = [
    "etc/datadog-agent/datadog.yaml",
    "etc/datadog.yaml",
    "etc/datadog-agent/conf.d",
]
FLARE_LOG_PATHS = [
    "var/log/datadog/agent.log",
    "var/log/datadog/trace-agent.log",
    "var/log/datadog/process-agent.log",
    "var/log/datadog/security-agent.log",
]
FLARE_STATUS_PATHS = [
    "status.log",
    "diagnose.log",
    "runtime_config_dump.yaml",
    "config-check.log",
    "tagger-list.log",
    "workload-list.log",
]

# Environment variables we care about in security investigations
SECURITY_ENV_VARS = [
    "DD_APPSEC_ENABLED",
    "DD_IAST_ENABLED",
    "DD_APPSEC_SCA_ENABLED",
    "DD_RUNTIME_SECURITY_CONFIG_ENABLED",
    "DD_SBOM_ENABLED",
    "DD_COMPLIANCE_CONFIG_ENABLED",
    "DD_SYSTEM_PROBE_ENABLED",
]


# ── Flare Analyzer (deterministic) ───────────────────────────────────────────

def _find_flare_dirs(assets_dir: Path) -> list[Path]:
    """Find extracted flare directories under assets/."""
    flare_dirs = []
    for d in assets_dir.iterdir():
        if not d.is_dir():
            continue
        # A flare typically has an etc/ or var/ subfolder, or a hostname subfolder that does
        if (d / "etc").exists() or (d / "var").exists():
            flare_dirs.append(d)
            continue
        for sub in d.iterdir():
            if sub.is_dir() and ((sub / "etc").exists() or (sub / "var").exists()):
                flare_dirs.append(sub)
    return flare_dirs


def _read_text_safe(path: Path, max_bytes: int = 500_000) -> str:
    """Read a text file, truncating if too large."""
    try:
        size = path.stat().st_size
        if size > max_bytes:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            return content + f"\n\n[...truncated, file is {size:,} bytes]"
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[Error reading file: {e}]"


def _extract_agent_version(flare_dir: Path) -> str:
    """Try to find the agent version from flare contents."""
    for candidate in ["version-history.log", "status.log"]:
        f = flare_dir / candidate
        if not f.exists():
            for match in flare_dir.rglob(candidate):
                f = match
                break
        if f.exists():
            content = _read_text_safe(f, 10_000)
            m = re.search(r"Agent\s*(?:version|v)[\s:]*(\d+\.\d+\.\d+\S*)", content, re.IGNORECASE)
            if m:
                return m.group(1)
    return "Unknown"


def _extract_env_vars(flare_dir: Path) -> dict[str, str]:
    """Search for security-relevant env vars in config/status files."""
    found = {}
    search_files = list(flare_dir.rglob("*.yaml")) + list(flare_dir.rglob("*.log"))
    for f in search_files[:30]:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")[:100_000]
        except Exception:
            continue
        for var in SECURITY_ENV_VARS:
            if var in found:
                continue
            m = re.search(rf"{var}\s*[=:]\s*(\S+)", content, re.IGNORECASE)
            if m:
                found[var] = m.group(1)
            elif var.lower().replace("dd_", "") in content.lower():
                # Check for YAML-style: appsec_enabled: true
                snake = var.lower().replace("dd_", "")
                m2 = re.search(rf"{snake}\s*:\s*(\S+)", content, re.IGNORECASE)
                if m2:
                    found[var] = m2.group(1)
    return found


def _extract_errors(flare_dir: Path, max_errors: int = 20) -> list[str]:
    """Extract ERROR/FATAL lines from log files in the flare."""
    errors = []
    for log_path in flare_dir.rglob("*.log"):
        try:
            content = log_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(log_path.relative_to(flare_dir))
        for line in content.split("\n"):
            if re.search(r"\b(ERROR|FATAL|PANIC)\b", line):
                cleaned = line.strip()[:300]
                if cleaned and cleaned not in errors:
                    errors.append(f"[{rel}] {cleaned}")
                    if len(errors) >= max_errors:
                        return errors
    return errors


def analyze_flare(flare_dir: Path) -> str:
    """Analyze a Datadog agent flare directory. Returns markdown section."""
    lines = [f"### Flare: `{flare_dir.name}`\n"]

    agent_version = _extract_agent_version(flare_dir)
    lines.append(f"**Agent Version:** {agent_version}\n")

    env_vars = _extract_env_vars(flare_dir)
    if env_vars:
        lines.append("**Security Config:**\n")
        for var, val in sorted(env_vars.items()):
            status = "enabled" if val.lower() in ("true", "1", "yes") else "disabled" if val.lower() in ("false", "0", "no") else val
            lines.append(f"- `{var}` = `{val}` ({status})")
        lines.append("")
    else:
        lines.append("**Security Config:** No security-related env vars detected in flare.\n")

    # Check for key config files
    config_files = []
    for pattern in ["datadog.yaml", "system-probe.yaml", "security-agent.yaml"]:
        for match in flare_dir.rglob(pattern):
            config_files.append(match)
    if config_files:
        lines.append("**Config Files Found:**")
        for cf in config_files[:10]:
            lines.append(f"- `{cf.relative_to(flare_dir)}`")
        lines.append("")

    errors = _extract_errors(flare_dir)
    if errors:
        lines.append(f"**Errors Found ({len(errors)}):**\n```")
        for err in errors:
            lines.append(err)
        lines.append("```\n")
    else:
        lines.append("**Errors:** No ERROR/FATAL lines found in logs.\n")

    # Diagnose output
    for diag_name in ["diagnose.log", "config-check.log"]:
        for diag in flare_dir.rglob(diag_name):
            content = _read_text_safe(diag, 5000)
            fail_lines = [l for l in content.split("\n") if re.search(r"(FAIL|ERROR|WARN)", l, re.IGNORECASE)]
            if fail_lines:
                lines.append(f"**{diag_name} issues ({len(fail_lines)}):**\n```")
                for fl in fail_lines[:15]:
                    lines.append(fl.strip()[:200])
                lines.append("```\n")
            break

    return "\n".join(lines)


# ── Image Analyzer (LLM-powered) ─────────────────────────────────────────────

def _analyze_image_gemini(image_path: Path) -> str:
    """Send an image to Gemini vision for analysis."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return ""

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        model = genai.GenerativeModel(model_name)

        image_data = image_path.read_bytes()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
        mime = mime_map.get(image_path.suffix.lower(), "image/png")

        response = model.generate_content([
            {
                "mime_type": mime,
                "data": image_data,
            },
            "You are analyzing a screenshot attached to a Datadog security support ticket. "
            "1) Extract ALL visible text (terminal output, error messages, config values, UI labels). "
            "2) Describe what the screenshot shows (UI, terminal, dashboard, etc.). "
            "3) Flag any error messages, warnings, misconfigurations, or notable values. "
            "Be concise and factual. Use markdown formatting.",
        ])
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        return f"[Image analysis failed: {e}]"

    return ""


def analyze_image(image_path: Path) -> str:
    """Analyze an image file. Returns markdown section."""
    result = _analyze_image_gemini(image_path)
    if not result:
        return f"### Image: `{image_path.name}`\n\n*No vision API available for image analysis. Set GEMINI_API_KEY in .env.*\n"
    return f"### Image: `{image_path.name}`\n\n{result}\n"


# ── Log Analyzer (regex + optional LLM) ──────────────────────────────────────

def analyze_log(log_path: Path) -> str:
    """Analyze a log file. Returns markdown section."""
    content = _read_text_safe(log_path, 200_000)
    lines = content.split("\n")

    section = [f"### Log: `{log_path.name}`\n"]
    section.append(f"**Size:** {log_path.stat().st_size:,} bytes, {len(lines):,} lines\n")

    # Extract error/warning lines
    errors = []
    warnings = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.search(r"\b(ERROR|FATAL|PANIC|EXCEPTION)\b", stripped, re.IGNORECASE):
            if stripped[:200] not in errors:
                errors.append(stripped[:200])
        elif re.search(r"\bWARN(ING)?\b", stripped, re.IGNORECASE):
            if stripped[:200] not in warnings:
                warnings.append(stripped[:200])

    if errors:
        section.append(f"**Errors ({len(errors)}):**\n```")
        for e in errors[:15]:
            section.append(e)
        if len(errors) > 15:
            section.append(f"... and {len(errors) - 15} more")
        section.append("```\n")

    if warnings:
        section.append(f"**Warnings ({len(warnings)}):**\n```")
        for w in warnings[:10]:
            section.append(w)
        if len(warnings) > 10:
            section.append(f"... and {len(warnings) - 10} more")
        section.append("```\n")

    if not errors and not warnings:
        section.append("No errors or warnings found.\n")

    # Extract version strings
    versions = set()
    for m in re.finditer(r"(?:version|v)[:\s]*(\d+\.\d+\.\d+\S*)", content[:50_000], re.IGNORECASE):
        versions.add(m.group(1))
    if versions:
        section.append("**Version strings found:** " + ", ".join(f"`{v}`" for v in sorted(versions)) + "\n")

    return "\n".join(section)


# ── CSV Analyzer (deterministic) ─────────────────────────────────────────────

def analyze_csv(csv_path: Path) -> str:
    """Analyze a CSV file. Returns markdown section."""
    section = [f"### Data: `{csv_path.name}`\n"]

    try:
        content = csv_path.read_text(encoding="utf-8", errors="replace")
        dialect = csv.Sniffer().sniff(content[:4096])
        reader = csv.reader(StringIO(content), dialect)
        rows = list(reader)
    except Exception:
        try:
            content = csv_path.read_text(encoding="utf-8", errors="replace")
            reader = csv.reader(StringIO(content))
            rows = list(reader)
        except Exception as e:
            section.append(f"*Could not parse CSV: {e}*\n")
            return "\n".join(section)

    if not rows:
        section.append("*Empty file.*\n")
        return "\n".join(section)

    headers = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []

    section.append(f"**Rows:** {len(data_rows):,} (+ header)")
    section.append(f"**Columns ({len(headers)}):** {', '.join(f'`{h}`' for h in headers[:20])}")
    if len(headers) > 20:
        section[-1] += f" ... and {len(headers) - 20} more"
    section.append("")

    # Show first few rows as a table
    if data_rows:
        preview_cols = min(6, len(headers))
        preview_rows = data_rows[:5]
        section.append("**Preview (first 5 rows):**\n")
        section.append("| " + " | ".join(headers[:preview_cols]) + " |")
        section.append("| " + " | ".join(["---"] * preview_cols) + " |")
        for row in preview_rows:
            cells = [(c[:40] + "..." if len(c) > 40 else c) for c in row[:preview_cols]]
            while len(cells) < preview_cols:
                cells.append("")
            section.append("| " + " | ".join(cells) + " |")
        section.append("")

    return "\n".join(section)


# ── Main Entry Point ─────────────────────────────────────────────────────────

def analyze_investigation(issue_key: str) -> Path | None:
    """Run all analyzers on an investigation's assets and write pre-analysis.md.

    Returns the path to the generated report, or None if no assets found.
    """
    inv_dir = INVESTIGATIONS_DIR / issue_key
    assets_dir = inv_dir / "assets"
    if not assets_dir.exists():
        return None

    sections = []
    sections.append(f"# Pre-Analysis: {issue_key}\n")
    sections.append(f"*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    sections.append("---\n")

    found_anything = False

    # 1. Analyze extracted flare directories
    flare_dirs = _find_flare_dirs(assets_dir)
    if flare_dirs:
        sections.append("## Flare Analysis\n")
        for fd in flare_dirs:
            sections.append(analyze_flare(fd))
            found_anything = True

    # 2. Analyze standalone images
    images = [f for f in assets_dir.iterdir()
              if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
    if images:
        sections.append("## Screenshot Analysis\n")
        for img in sorted(images):
            sections.append(analyze_image(img))
            found_anything = True

    # 3. Analyze standalone log files (not inside flares)
    flare_paths = {str(fd) for fd in flare_dirs}
    logs = []
    for f in assets_dir.iterdir():
        if f.is_file() and f.suffix.lower() in LOG_EXTENSIONS:
            logs.append(f)
    if logs:
        sections.append("## Log Analysis\n")
        for log in sorted(logs):
            sections.append(analyze_log(log))
            found_anything = True

    # 4. Analyze CSV files
    csvs = [f for f in assets_dir.iterdir()
            if f.is_file() and f.suffix.lower() in CSV_EXTENSIONS]
    if csvs:
        sections.append("## Data Analysis\n")
        for c in sorted(csvs):
            sections.append(analyze_csv(c))
            found_anything = True

    if not found_anything:
        return None

    report_path = inv_dir / "pre-analysis.md"
    report_path.write_text("\n".join(sections), encoding="utf-8")
    return report_path
