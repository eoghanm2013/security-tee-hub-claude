"""
Asset handler for TEE Hub.

Downloads JIRA attachments, extracts archives (flares), and manages
local asset storage in investigations/SCRS-XXXX/assets/.
"""

import os
import json
import shutil
import base64
import zipfile
import tarfile
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
INVESTIGATIONS_DIR = ROOT / "investigations"
TEMPLATE_DIR = INVESTIGATIONS_DIR / ".template"

ARCHIVE_EXTENSIONS = {".zip", ".gz", ".tgz", ".tar", ".bz2"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


# ── JIRA Auth (same pattern as tools.py) ─────────────────────────────────────

def _jira_auth_header() -> str:
    email = os.environ.get("ATLASSIAN_EMAIL", "")
    token = os.environ.get("ATLASSIAN_API_TOKEN", "")
    if not email or not token:
        return ""
    return base64.b64encode(f"{email}:{token}".encode()).decode()


def _jira_domain() -> str:
    return os.environ.get("ATLASSIAN_DOMAIN", "datadoghq.atlassian.net")


def _jira_get_json(endpoint: str) -> dict:
    auth = _jira_auth_header()
    if not auth:
        return {"error": "JIRA credentials not configured"}
    url = f"https://{_jira_domain()}/rest/api/3/{endpoint}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"JIRA API error {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": f"JIRA connection failed: {e}"}


def _jira_download_binary(url: str, dest: Path) -> Path:
    """Download a binary file from JIRA (attachment content URL)."""
    auth = _jira_auth_header()
    if not auth:
        raise RuntimeError("JIRA credentials not configured")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {auth}",
        "Accept": "application/octet-stream",
    })
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
    return dest


# ── Investigation Folder Management ──────────────────────────────────────────

def _ensure_investigation_dir(issue_key: str) -> Path:
    """Create investigation folder from template if it doesn't exist."""
    inv_dir = INVESTIGATIONS_DIR / issue_key
    if inv_dir.exists():
        return inv_dir

    inv_dir.mkdir(parents=True, exist_ok=True)
    (inv_dir / "assets").mkdir(exist_ok=True)

    if TEMPLATE_DIR.exists():
        for template_file in TEMPLATE_DIR.iterdir():
            if template_file.is_file() and not template_file.name.startswith("."):
                dest = inv_dir / template_file.name
                if not dest.exists():
                    content = template_file.read_text(encoding="utf-8")
                    content = content.replace("SCRS-XXXX", issue_key)
                    dest.write_text(content, encoding="utf-8")

    meta_path = inv_dir / "meta.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps({
            "status": "investigating",
            "assignee": "",
        }, indent=2) + "\n", encoding="utf-8")

    return inv_dir


# ── Public API ───────────────────────────────────────────────────────────────

def list_attachments(issue_key: str) -> dict:
    """Fetch attachment metadata from JIRA for a given issue.

    Returns:
        {
            "attachments": [
                {
                    "id": "12345",
                    "filename": "agent-flare.zip",
                    "mimeType": "application/zip",
                    "size": 2048576,
                    "content_url": "https://...",
                    "created": "2026-03-01T14:22:00.000+0000",
                    "author": "John Smith",
                },
                ...
            ],
            "error": None
        }
    """
    data = _jira_get_json(f"issue/{issue_key}?fields=attachment")
    if "error" in data:
        return {"attachments": [], "error": data["error"]}

    raw_attachments = data.get("fields", {}).get("attachment", []) or []
    attachments = []
    for att in raw_attachments:
        attachments.append({
            "id": str(att.get("id", "")),
            "filename": att.get("filename", "unknown"),
            "mimeType": att.get("mimeType", "application/octet-stream"),
            "size": att.get("size", 0),
            "content_url": att.get("content", ""),
            "created": att.get("created", ""),
            "author": att.get("author", {}).get("displayName", "Unknown"),
        })

    return {"attachments": attachments, "error": None}


def get_local_assets(issue_key: str) -> list[dict]:
    """List files already downloaded to the investigation's assets folder."""
    assets_dir = INVESTIGATIONS_DIR / issue_key / "assets"
    if not assets_dir.exists():
        return []

    assets = []
    for f in sorted(assets_dir.rglob("*")):
        if not f.is_file() or f.name.startswith("."):
            continue
        suffix = f.suffix.lower()
        assets.append({
            "name": f.name,
            "relative_path": str(f.relative_to(INVESTIGATIONS_DIR / issue_key / "assets")),
            "size": f.stat().st_size,
            "is_image": suffix in IMAGE_EXTENSIONS,
            "is_archive": suffix in ARCHIVE_EXTENSIONS,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return assets


def download_attachment(issue_key: str, attachment: dict) -> Path:
    """Download a single JIRA attachment to the investigation's assets folder.

    Args:
        issue_key: e.g. "SCRS-1967"
        attachment: dict with at least "filename" and "content_url" keys

    Returns:
        Path to the downloaded file.
    """
    inv_dir = _ensure_investigation_dir(issue_key)
    assets_dir = inv_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    filename = attachment["filename"]
    dest = assets_dir / filename

    # Avoid re-downloading if file exists with same size
    if dest.exists() and dest.stat().st_size == attachment.get("size", -1):
        return dest

    _jira_download_binary(attachment["content_url"], dest)
    return dest


def extract_archive(archive_path: Path) -> Path | None:
    """Extract a zip or tar archive into a subfolder next to it.

    Returns the extraction directory, or None if not an archive.
    """
    suffix = archive_path.suffix.lower()
    name_stem = archive_path.stem
    if suffix == ".gz" and name_stem.endswith(".tar"):
        name_stem = Path(name_stem).stem

    extract_dir = archive_path.parent / name_stem
    if extract_dir.exists():
        return extract_dir

    try:
        if suffix == ".zip":
            with zipfile.ZipFile(archive_path, "r") as zf:
                for member in zf.namelist():
                    member_path = (extract_dir / member).resolve()
                    if not str(member_path).startswith(str(extract_dir.resolve())):
                        raise ValueError(f"Zip entry escapes target directory: {member}")
                zf.extractall(extract_dir)
            return extract_dir

        if suffix in (".gz", ".tgz", ".tar", ".bz2"):
            mode = "r:gz" if suffix in (".gz", ".tgz") else "r:bz2" if suffix == ".bz2" else "r"
            with tarfile.open(archive_path, mode) as tf:
                tf.extractall(extract_dir, filter="data")
            return extract_dir
    except Exception as e:
        print(f"[asset_handler] Failed to extract {archive_path.name}: {e}")
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)

    return None


def download_all_new(issue_key: str) -> dict:
    """Download all new JIRA attachments for an issue and extract archives.

    Returns:
        {
            "downloaded": [{"filename": ..., "path": ..., "extracted_to": ...}, ...],
            "skipped": [{"filename": ..., "reason": ...}, ...],
            "error": str | None
        }
    """
    result = {"downloaded": [], "skipped": [], "error": None}

    att_data = list_attachments(issue_key)
    if att_data["error"]:
        result["error"] = att_data["error"]
        return result

    if not att_data["attachments"]:
        return result

    assets_dir = INVESTIGATIONS_DIR / issue_key / "assets"
    existing_files = set()
    if assets_dir.exists():
        existing_files = {f.name for f in assets_dir.iterdir() if f.is_file()}

    for att in att_data["attachments"]:
        filename = att["filename"]

        if filename in existing_files:
            local_path = assets_dir / filename
            if local_path.stat().st_size == att.get("size", -1):
                result["skipped"].append({
                    "filename": filename,
                    "reason": "already downloaded (same size)",
                })
                continue

        try:
            dest = download_attachment(issue_key, att)
            entry = {
                "filename": filename,
                "path": str(dest.relative_to(ROOT)),
                "extracted_to": None,
            }

            if dest.suffix.lower() in ARCHIVE_EXTENSIONS:
                extract_dir = extract_archive(dest)
                if extract_dir:
                    entry["extracted_to"] = str(extract_dir.relative_to(ROOT))

            result["downloaded"].append(entry)
        except Exception as e:
            result["skipped"].append({
                "filename": filename,
                "reason": f"download failed: {e}",
            })

    return result
