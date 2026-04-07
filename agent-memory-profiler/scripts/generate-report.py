#!/usr/bin/env python3
"""Generate a shareable HTML report from Datadog Security Memory Profiler CSV.

Usage:
    python3 scripts/generate-report.py results/profile_20260226_143000.csv
    python3 scripts/generate-report.py   # uses latest CSV in results/

Produces an HTML file alongside the CSV that can be attached to JIRA tickets.
"""

import csv
import os
import sys
from collections import defaultdict, OrderedDict
from datetime import datetime

AGENT_FEATURE_NAMES = {
    "agent_baseline": "Baseline (no security)",
    "agent_cws": "Workload Protection (CWS)",
    "agent_sbom_host": "VM: Host SBOM",
    "agent_sbom_containers": "VM: Container Image SBOM",
    "agent_cspm": "CSPM: Compliance Benchmarks",
}

TRACER_FEATURE_NAMES = {
    "aap": "AAP (App & API Protection)",
    "iast": "IAST",
    "sca": "SCA Runtime",
}

LANG_LABELS = {
    "python": "Python (dd-trace-py)",
    "node": "Node.js (dd-trace-js)",
    "java": "Java (dd-trace-java)",
    "php": "PHP (dd-trace-php)",
}


def load_csv(path):
    """Load CSV into phase groups. Returns dict of phase -> list of samples."""
    phases = OrderedDict()
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            phase = row["phase"]
            mb = int(row["memory_mb"])
            lang = row.get("tracer_language", "")
            container = row.get("container", "")
            ts = int(row["timestamp"])
            if phase not in phases:
                phases[phase] = []
            phases[phase].append({"ts": ts, "mb": mb, "lang": lang, "container": container})
    return phases


def stats(samples):
    mbs = [s["mb"] for s in samples]
    if not mbs:
        return {"avg": 0, "min": 0, "max": 0, "count": 0}
    return {
        "avg": sum(mbs) // len(mbs),
        "min": min(mbs),
        "max": max(mbs),
        "count": len(mbs),
    }


def trend_indicator(samples):
    if len(samples) < 6:
        return "insufficient_data"
    mbs = [s["mb"] for s in samples]
    q = len(mbs) // 4
    if q == 0:
        return "insufficient_data"
    first_q = sum(mbs[:q]) / q
    last_q = sum(mbs[-q:]) / q
    delta_pct = ((last_q - first_q) / max(first_q, 1)) * 100
    if delta_pct > 10:
        return "growing"
    elif delta_pct < -5:
        return "shrinking"
    return "stable"


TREND_BADGES = {
    "growing": '<span class="badge badge-danger">GROWING</span>',
    "stable": '<span class="badge badge-success">STABLE</span>',
    "shrinking": '<span class="badge badge-info">SHRINKING</span>',
    "insufficient_data": '<span class="badge badge-muted">N/A</span>',
}


def generate_html(phases, csv_path):
    # Separate agent and tracer phases
    agent_phases = {k: v for k, v in phases.items() if k.startswith("agent_")}
    tracer_phases = {k: v for k, v in phases.items() if k.startswith("tracer_")}

    agent_baseline = stats(agent_phases.get("agent_baseline", []))
    agent_feature_phases = {k: v for k, v in agent_phases.items() if k != "agent_baseline"}

    # Build tracer baselines per language
    tracer_baselines = {}
    tracer_feature_data = {}
    for phase_key, samples in tracer_phases.items():
        if phase_key == "tracer_baseline":
            for sample in samples:
                lang = sample["lang"]
                if lang not in tracer_baselines:
                    tracer_baselines[lang] = []
                tracer_baselines[lang].append(sample)
        else:
            parts = phase_key.replace("tracer_", "").split("_", 1)
            if len(parts) == 2:
                lang, fid = parts
                tracer_feature_data[(lang, fid)] = samples

    # ---- Agent section HTML ----
    agent_rows = ""
    agent_chart_datasets = ""
    colors = ["#632CA6", "#FF6F61", "#2D8CFF", "#F5A623", "#7B68EE", "#00C49F", "#FF6384", "#36A2EB"]
    color_idx = 0

    if agent_baseline["count"] > 0:
        agent_rows += f"""
        <tr class="baseline-row">
            <td>Baseline (no security)</td>
            <td>{agent_baseline['avg']}MB</td>
            <td>-</td><td>-</td>
            <td>{agent_baseline['min']}-{agent_baseline['max']}MB</td>
            <td>{TREND_BADGES.get(trend_indicator(agent_phases.get('agent_baseline', [])), '')}</td>
        </tr>"""

        c = colors[color_idx % len(colors)]
        data = [s["mb"] for s in agent_phases.get("agent_baseline", [])]
        agent_chart_datasets += f"{{label:'Baseline',data:{data},borderColor:'{c}',borderWidth:2,pointRadius:1,fill:false}},"
        color_idx += 1

    for phase_key, samples in agent_feature_phases.items():
        s = stats(samples)
        name = AGENT_FEATURE_NAMES.get(phase_key, phase_key)
        delta = s["avg"] - agent_baseline["avg"] if agent_baseline["avg"] else 0
        pct = (delta / agent_baseline["avg"] * 100) if agent_baseline["avg"] else 0
        t = trend_indicator(samples)
        agent_rows += f"""
        <tr>
            <td>{name}</td>
            <td>{s['avg']}MB</td>
            <td>+{delta}MB</td>
            <td>+{pct:.1f}%</td>
            <td>{s['min']}-{s['max']}MB</td>
            <td>{TREND_BADGES.get(t, '')}</td>
        </tr>"""

        c = colors[color_idx % len(colors)]
        data = [sam["mb"] for sam in samples]
        agent_chart_datasets += f"{{label:'{name}',data:{data},borderColor:'{c}',borderWidth:2,pointRadius:1,fill:false}},"
        color_idx += 1

    # ---- Tracer section HTML ----
    tracer_rows = ""
    tracer_chart_datasets = ""
    color_idx = 0

    for lang in sorted(tracer_baselines.keys()):
        bl_samples = tracer_baselines[lang]
        bl = stats(bl_samples)
        lang_label = LANG_LABELS.get(lang, lang)

        tracer_rows += f"""
        <tr class="baseline-row">
            <td>{lang_label} Baseline</td>
            <td>{lang}</td>
            <td>{bl['avg']}MB</td>
            <td>-</td><td>-</td>
            <td>{TREND_BADGES.get(trend_indicator(bl_samples), '')}</td>
        </tr>"""

        for fid, flabel in TRACER_FEATURE_NAMES.items():
            key = (lang, fid)
            if key in tracer_feature_data:
                samples = tracer_feature_data[key]
                s = stats(samples)
                delta = s["avg"] - bl["avg"]
                pct = (delta / bl["avg"] * 100) if bl["avg"] else 0
                t = trend_indicator(samples)
                tracer_rows += f"""
        <tr>
            <td>{flabel}</td>
            <td>{lang}</td>
            <td>{s['avg']}MB</td>
            <td>+{delta}MB</td>
            <td>+{pct:.1f}%</td>
            <td>{TREND_BADGES.get(t, '')}</td>
        </tr>"""

                c = colors[color_idx % len(colors)]
                data = [sam["mb"] for sam in samples]
                tracer_chart_datasets += f"{{label:'{lang} + {flabel}',data:{data},borderColor:'{c}',borderWidth:2,pointRadius:1,fill:false}},"
                color_idx += 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Determine max chart length
    all_lengths = [len(v) for v in phases.values()]
    max_len = max(all_lengths) if all_lengths else 0

    has_agent = bool(agent_feature_phases)
    has_tracer = bool(tracer_feature_data)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Security Memory Profile - {now}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #333; padding: 24px; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ color: #632CA6; margin-bottom: 4px; font-size: 24px; }}
    .subtitle {{ color: #666; margin-bottom: 24px; font-size: 14px; }}
    .card {{ background: white; border-radius: 8px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    .card h2 {{ color: #632CA6; font-size: 18px; margin-bottom: 16px; }}
    .section-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #999; margin-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th {{ background: #f1f1f1; padding: 10px 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #ddd; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
    tr:hover td {{ background: #f9f6ff; }}
    .baseline-row {{ background: #f0ebf8; font-weight: 600; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
    .badge-success {{ background: #d4edda; color: #155724; }}
    .badge-danger {{ background: #f8d7da; color: #721c24; }}
    .badge-info {{ background: #d1ecf1; color: #0c5460; }}
    .badge-muted {{ background: #e2e3e5; color: #383d41; }}
    .chart-container {{ height: 350px; }}
    .meta {{ display: flex; gap: 24px; margin-bottom: 16px; font-size: 13px; color: #666; }}
    .meta strong {{ color: #333; }}
    .tips {{ margin-top: 12px; }}
    .tips li {{ margin: 6px 0; line-height: 1.5; }}
</style>
</head>
<body>
<div class="container">
    <h1>Datadog Security Memory Profile</h1>
    <p class="subtitle">Generated {now} from {os.path.basename(csv_path)}</p>
"""

    if has_agent:
        html += f"""
    <div class="card">
        <p class="section-label">Agent-side</p>
        <h2>Agent Security Features</h2>
        <div class="meta">
            <div><strong>Baseline:</strong> {agent_baseline['avg']}MB avg</div>
            <div><strong>Samples per phase:</strong> {agent_baseline['count']}</div>
        </div>
        <table>
            <thead><tr><th>Feature</th><th>Avg Memory</th><th>Delta</th><th>Growth</th><th>Range</th><th>Trend</th></tr></thead>
            <tbody>{agent_rows}</tbody>
        </table>
    </div>
    <div class="card">
        <h2>Agent Memory Over Time</h2>
        <div class="chart-container"><canvas id="agentChart"></canvas></div>
    </div>
"""

    if has_tracer:
        html += f"""
    <div class="card">
        <p class="section-label">Tracer-side</p>
        <h2>Tracer Security Features (per language)</h2>
        <table>
            <thead><tr><th>Feature</th><th>Language</th><th>Avg Memory</th><th>Delta</th><th>Growth</th><th>Trend</th></tr></thead>
            <tbody>{tracer_rows}</tbody>
        </table>
    </div>
    <div class="card">
        <h2>Tracer Memory Over Time</h2>
        <div class="chart-container"><canvas id="tracerChart"></canvas></div>
    </div>
"""

    html += f"""
    <div class="card">
        <h2>How to Read This Report</h2>
        <ul class="tips">
            <li><strong>Agent-side features</strong> (CWS, CSPM, VM/SBOM) run inside the dd-agent container. Their memory impact is measured on the agent.</li>
            <li><strong>Tracer-side features</strong> (AAP, IAST, SCA) run inside the application process via dd-trace. Their memory impact is measured on the app container, not the agent.</li>
            <li><strong>Trend: STABLE</strong> means memory leveled off. This is expected.</li>
            <li><strong>Trend: GROWING</strong> means memory was still climbing. Run a longer test (--duration 1800) to confirm plateau or leak.</li>
            <li>If escalating, attach this report + an agent flare + the CSV to the JIRA ticket.</li>
            <li><a href="https://docs.datadoghq.com/agent/troubleshooting/agent-resource-usage/">Agent Resource Usage docs</a></li>
        </ul>
    </div>
</div>

<script>
"""

    if has_agent:
        html += f"""
new Chart(document.getElementById('agentChart'), {{
    type: 'line',
    data: {{
        labels: Array.from({{length: {max_len}}}, (_, i) => i * 10 + 's'),
        datasets: [{agent_chart_datasets}]
    }},
    options: {{
        responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12, padding: 16 }} }} }},
        scales: {{
            y: {{ title: {{ display: true, text: 'Agent Memory (MB)' }}, beginAtZero: false }},
            x: {{ title: {{ display: true, text: 'Time' }}, ticks: {{ maxTicksLimit: 15 }} }}
        }}
    }}
}});
"""

    if has_tracer:
        html += f"""
new Chart(document.getElementById('tracerChart'), {{
    type: 'line',
    data: {{
        labels: Array.from({{length: {max_len}}}, (_, i) => i * 10 + 's'),
        datasets: [{tracer_chart_datasets}]
    }},
    options: {{
        responsive: true, maintainAspectRatio: false,
        plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12, padding: 16 }} }} }},
        scales: {{
            y: {{ title: {{ display: true, text: 'App Memory (MB)' }}, beginAtZero: false }},
            x: {{ title: {{ display: true, text: 'Time' }}, ticks: {{ maxTicksLimit: 15 }} }}
        }}
    }}
}});
"""

    html += """
</script>
</body>
</html>"""

    return html


def main():
    if len(sys.argv) < 2:
        results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
        csvs = sorted(
            [f for f in os.listdir(results_dir) if f.endswith(".csv")],
            reverse=True,
        )
        if not csvs:
            print("Usage: python3 scripts/generate-report.py <csv_file>")
            print("No CSV files found in results/")
            sys.exit(1)
        csv_path = os.path.join(results_dir, csvs[0])
        print(f"Using latest: {csv_path}")
    else:
        csv_path = sys.argv[1]

    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        sys.exit(1)

    phases = load_csv(csv_path)
    html = generate_html(phases, csv_path)

    out_path = csv_path.replace(".csv", ".html")
    with open(out_path, "w") as f:
        f.write(html)

    print(f"Report generated: {out_path}")
    print(f"Open in browser: file://{os.path.abspath(out_path)}")


if __name__ == "__main__":
    main()
