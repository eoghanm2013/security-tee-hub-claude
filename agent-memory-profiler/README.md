# Datadog Security Memory Profiler

Measures the memory impact of Datadog Security features on the agent and application tracers. Built for TSEs investigating "we enabled X and memory went up" escalations.

Covers both sides of the stack:
- **Agent-side:** Workload Protection (CWS), CSPM, VM/SBOM
- **Tracer-side:** AAP (AppSec), IAST, SCA across Python, Node, Java, and PHP

## Quick Start

```bash
git clone https://github.com/DataDog/security-memory-profiler.git
cd security-memory-profiler

cp .env.example .env
# Edit .env and set DD_API_KEY

./profile.sh
```

## What It Tests

### Agent-side security features

These run inside the dd-agent container. Memory is measured on the agent.

| ID | Feature | Product Area | What It Does |
|----|---------|-------------|-------------|
| `cws` | Workload Protection (CWS) | Threat Management | eBPF-based process, file, and network monitoring |
| `sbom_host` | VM: Host SBOM | Cloud Security | Scans host OS packages for CVEs |
| `sbom_containers` | VM: Container Image SBOM | Cloud Security | Scans container images for CVEs |
| `cspm` | CSPM: Compliance Benchmarks | Cloud Security | CIS benchmarks and host compliance |

### Tracer-side security features

These run inside the application process via dd-trace. Memory is measured on the app container, not the agent. Tested per language.

| ID | Feature | Product Area | What It Does |
|----|---------|-------------|-------------|
| `aap` | AAP (App & API Protection) | Threat Management | In-App WAF, attack detection, IP/user blocking |
| `iast` | IAST | Code Security | Source-to-sink taint tracking for exploitable code paths |
| `sca` | SCA Runtime | Code Security | Runtime detection of vulnerable third-party libraries |

**Languages tested:** Python (dd-trace-py), Node.js (dd-trace-js), Java (dd-trace-java), PHP (dd-trace-php)

## Usage

### Full profile (everything)

```bash
./profile.sh
```

Tests all 4 agent features + all 3 tracer features across all 4 languages. Takes ~40 minutes with default 3-minute phases.

### Agent features only

```bash
./profile.sh --category agent
```

### Tracer features only

```bash
./profile.sh --category tracer
```

### Single language

```bash
./profile.sh --category tracer --tracer python
./profile.sh --category tracer --tracer java
./profile.sh --tracer php                        # implies --category tracer if no agent feature specified
```

### Single feature

```bash
./profile.sh --feature cws                       # Agent: CWS only
./profile.sh --feature aap --tracer java          # Tracer: AAP on Java only
./profile.sh --feature iast                       # Tracer: IAST on all languages
```

### Longer duration (leak detection)

```bash
./profile.sh --feature cws --duration 1800        # 30 min sample window
./profile.sh --feature aap --tracer node --duration 600
```

### Monitor an existing container

```bash
./profile.sh --monitor-only --container my-agent-container --duration 600
```

### Generate HTML report

```bash
python3 scripts/generate-report.py results/profile_YYYYMMDD_HHMMSS.csv
```

## Output

### Terminal summary

```
--- Agent-side Security Features ---
Feature                                  | Baseline MB | With Feature MB | Delta MB | Growth %
-----------------------------------------|-------------|-----------------|----------|--------
Workload Protection (CWS)               | 142         | 198             | +56      | +39%
VM: Host SBOM                            | 142         | 167             | +25      | +18%
VM: Container Image SBOM                 | 142         | 151             | +9       | +6%
CSPM: Compliance Benchmarks              | 142         | 155             | +13      | +9%

--- Tracer-side Security Features ---
Feature                                  | Language | Baseline MB | With Feature MB | Delta MB | Growth %
-----------------------------------------|----------|-------------|-----------------|----------|--------
AAP (App & API Protection)               | python   | 85          | 142             | +57      | +67%
AAP (App & API Protection)               | node     | 120         | 195             | +75      | +62%
AAP (App & API Protection)               | java     | 210         | 340             | +130     | +62%
AAP (App & API Protection)               | php      | 45          | 68              | +23      | +51%
IAST                                     | python   | 85          | 155             | +70      | +82%
...
```

### HTML report

Interactive chart with per-feature memory over time, split into agent-side and tracer-side sections. Attach to JIRA tickets.

### CSV

Raw time-series data in `results/profile_YYYYMMDD_HHMMSS.csv`.

## Expected Memory Ranges

### Agent-side

| Feature | Typical Delta | Notes |
|---------|-------------|-------|
| CWS | +40-80MB | eBPF maps and event buffers |
| SBOM Host | +15-40MB | Spikes during periodic scan, then drops |
| SBOM Container | +10-30MB | Per-image scan overhead |
| CSPM | +10-20MB | Periodic benchmark checks |
| All agent security | +80-170MB above baseline | Combined |

### Tracer-side (varies by language)

| Feature | Python | Node | Java | PHP |
|---------|--------|------|------|-----|
| AAP (WAF) | +30-60MB | +40-80MB | +80-150MB | +15-30MB |
| IAST | +40-80MB | +50-100MB | +100-200MB | +20-40MB |
| SCA | +5-15MB | +5-15MB | +10-25MB | +3-10MB |

Java tracers are heavier because the JVM allocates more aggressively. PHP is lightest because of its shared-nothing architecture (memory is per-request). These are typical ranges with moderate traffic.

## Requirements

- Docker and Docker Compose v2
- A Datadog API key
- Linux host recommended for agent-side features (eBPF needs a real kernel)
- macOS Docker Desktop works for tracer-side features

## Limitations

- **macOS Docker Desktop:** eBPF features (CWS) may not work correctly. Tracer-side features work fine.
- **Memory is container RSS.** Kernel-side eBPF map memory isn't captured by container stats.
- **Tracer memory varies by workload.** This tool uses minimal traffic for consistent comparison. Real apps with higher throughput will use more.
- **Java startup.** The Java app takes longer to stabilize due to JVM warmup. The profiler accounts for this with the stabilization wait.

## Slack Channels

- #support-security-threats (CWS, AAP)
- #support-cloud-security (CSPM, VM/SBOM)
- #support-code-security (IAST, SCA)

## License

Internal Datadog use only.
