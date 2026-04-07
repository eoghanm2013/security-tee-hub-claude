# TSE Guide: Security Feature Memory Investigations

## When to Use This Tool

Customer says some version of:
- "Memory went up after enabling ASM/AppSec/CWS/IAST/SCA"
- "Agent keeps getting OOMKilled since we turned on a security feature"
- "system-probe is using too much memory"
- "Our app's memory doubled after enabling dd-trace with appsec"
- "Memory keeps growing and never comes back down"

## The #1 Thing to Understand

Security features live in two different places, and this is the most common source of confusion:

**Agent-side features** (CWS, CSPM, VM/SBOM) run inside the dd-agent container. They affect **agent** memory.

**Tracer-side features** (AAP/AppSec, IAST, SCA) run inside the **application process** via dd-trace. They affect **app** memory, not agent memory.

If a customer says "we enabled ASM and the agent is using more memory," they're probably looking at the wrong container. ASM (AAP) runs in the app process. The agent might see slightly more trace data, but the real memory impact is on the application.

## Before You Start

### What to collect from the customer

- [ ] **Which feature was enabled** (exact env var: `DD_APPSEC_ENABLED`, `DD_IAST_ENABLED`, etc.)
- [ ] **Which process has high memory** (agent container? app container? system-probe?)
- [ ] **Tracer language and version** (for tracer-side features)
- [ ] **Agent version**
- [ ] **Memory limit** set in their orchestrator
- [ ] **Container/pod count** the agent monitors
- [ ] **Timeline**: when feature enabled vs when spike observed
- [ ] **Agent flare** (`agent flare`)

### Quick sanity check: are their limits too low?

**Agent-side limits:**

| Feature Set | Minimum |
|------------|---------|
| APM + Logs (no security) | 256MB |
| + CWS | 512MB |
| + CWS + CSPM + SBOM | 768MB |
| All agent security features | 1GB |

**Tracer-side limits (app process):**

Tracer-side features run in the app, so there's no universal limit. But as a rough guide, enabling AAP + IAST together typically adds:
- Python: +70-140MB to the app process
- Node: +90-180MB
- Java: +180-350MB
- PHP: +35-70MB (per-worker, shared-nothing model)

## Running the Profiler

### Setup (one time)

```bash
git clone https://github.com/DataDog/security-memory-profiler.git
cd security-memory-profiler
cp .env.example .env
# Set DD_API_KEY in .env
```

### Scenario 1: "Agent memory went up after enabling CWS/CSPM/SBOM"

This is an agent-side feature. Test it directly:

```bash
./profile.sh --feature cws          # Workload Protection
./profile.sh --feature cspm         # Compliance benchmarks
./profile.sh --feature sbom_host    # Host SBOM scanning
```

**Reading the results:**
- Delta under 80MB for CWS? Normal.
- Delta under 40MB for SBOM? Normal. Check if it drops after the scan cycle.
- Trend: GROWING after 10+ minutes? Run longer: `--duration 1800`

### Scenario 2: "App memory went up after enabling ASM/IAST/SCA"

This is a tracer-side feature. Test the customer's language:

```bash
# Customer is on Python
./profile.sh --feature aap --tracer python

# Customer is on Java with IAST
./profile.sh --feature iast --tracer java

# Not sure which feature? Test all three on their language
./profile.sh --category tracer --tracer php
```

**Reading the results:**
- Java + AAP adding 100-150MB? Normal. JVM allocates aggressively for WAF rules.
- Python + IAST adding 60-80MB? Normal. Taint tracking has per-request overhead.
- PHP + SCA adding 5-10MB? Normal. SCA is lightweight, just scans loaded extensions.
- Any tracer growing without plateau over 30 min? Likely a leak. Escalate.

### Scenario 3: "Memory keeps growing, never stabilizes"

Run a long test to detect a genuine leak:

```bash
./profile.sh --feature cws --duration 1800         # 30 min, agent-side
./profile.sh --feature aap --tracer node --duration 1800  # 30 min, tracer-side
```

If the trend is still GROWING after 30 minutes, this is likely a real leak. Escalate with:
- The CSV from `results/`
- An agent flare
- The HTML report from `python3 scripts/generate-report.py`

### Scenario 4: "Not sure which feature is causing it"

Run everything:

```bash
./profile.sh                    # All features, all languages (~40 min)
./profile.sh --category agent   # Just agent features (~15 min)
./profile.sh --category tracer --tracer java  # Just tracer features on Java (~15 min)
```

### Scenario 5: Monitor an existing setup

If you've already reproduced the customer's environment:

```bash
./profile.sh --monitor-only --container <container_name> --duration 600
```

## Generating a Report

```bash
python3 scripts/generate-report.py results/profile_YYYYMMDD_HHMMSS.csv
```

This produces an HTML file with charts showing memory over time, split into agent-side and tracer-side sections. Attach it to the ticket.

## What's Normal vs What's a Bug

### Normal behavior (tell the customer)

- CWS adds 40-80MB to the agent. eBPF programs maintain kernel-side data structures.
- SBOM causes periodic 15-40MB spikes during scan, then drops back.
- AAP/AppSec adds 30-150MB to the app process depending on language. The WAF needs to load and evaluate rules.
- IAST adds 40-200MB depending on language. Taint tracking monitors data flow through the application.
- SCA is lightweight (5-25MB). It scans loaded libraries at startup.
- Java tracers are always heavier than Python/Node/PHP. JVM overhead is real.
- Memory grows linearly with containers/services monitored (agent-side).

### Probably a bug (escalate)

- Memory growing continuously (no plateau) for 30+ minutes
- Agent exceeding 1GB with only CWS enabled and moderate workload
- App process exceeding 2x its baseline with just AAP enabled
- SBOM memory spike that never drops back
- Disabling the feature doesn't bring memory back to expected range
- Specific tracer version known to have issues (check release notes)

## Language-Specific Notes

### Python (dd-trace-py)
- Moderate overhead. GC handles cleanup well.
- IAST taint tracking adds per-request overhead but memory is generally stable.
- SCA runs at import time, minimal ongoing cost.

### Node.js (dd-trace-js)
- V8 heap management can cause memory to appear higher than actual usage.
- AAP WAF rules are loaded into the V8 heap.
- Watch for `--max-old-space-size` limits conflicting with security feature overhead.

### Java (dd-trace-java)
- Heaviest tracer by far. JVM metaspace + heap for WAF rules and taint tracking.
- `-Xmx` and `-Xms` settings directly affect how much memory the JVM claims.
- IAST is particularly heavy on Java. Adding 150-200MB is not unusual.
- Startup is slower. Give extra stabilization time.

### PHP (dd-trace-php)
- Lightest tracer. Shared-nothing model means each request starts fresh.
- IAST overhead is per-request, not cumulative.
- Memory "leaks" in PHP are often per-worker leaks that reset on worker recycle.
- Check `pm.max_requests` (PHP-FPM) if memory appears to grow.

## Escalation Template

```
**Issue:** [app/agent] memory [behavior] after enabling [feature]

**Feature enabled:** [env var, e.g., DD_APPSEC_ENABLED=true]
**Tracer:** [language] [version] (for tracer-side features)
**Agent version:** [version]
**Customer environment:** [k8s/ecs/host, container count]
**Memory limit set:** [their limit]

**Reproduction with security-memory-profiler:**
- Baseline: XXX MB
- With feature: XXX MB (+XX MB, +XX%)
- Trend: [STABLE/GROWING] over [duration]

**Attached:**
- Memory profile CSV + HTML report
- Agent flare: [ticket/ID]

**Routing:** [#support-security-threats / #support-cloud-security / #support-code-security]
```

## Common Misconfigurations

| Customer Says | Actual Issue | Fix |
|--------------|-------------|-----|
| "Agent OOMKilled after enabling CWS" | Memory limit at 256MB | Increase to 512MB+ |
| "App memory doubled with ASM" | Expected. WAF rules + request inspection cost memory. | Increase app memory limit. |
| "system-probe using 300MB" | CWS eBPF programs are running | Expected for CWS. |
| "SBOM spikes every few hours" | SBOM scan cycle | Expected. Should drop after scan. |
| "Java app using 500MB more with IAST" | JVM allocates aggressively for taint tracking | Expected for Java. Not a leak if stable. |
| "PHP memory growing per request" | PHP-FPM workers accumulating state | Set `pm.max_requests` to recycle workers. |
| "Enabling ASM increased agent memory" | ASM runs in the tracer, not the agent | Check app container memory instead. |

## Limitations

- **macOS Docker Desktop:** CWS won't work (needs real Linux kernel). Tracer features work fine.
- **Container RSS only.** Kernel eBPF map memory not captured.
- **Minimal traffic.** Real apps with higher throughput will use more tracer memory. This tool gives relative comparisons.
