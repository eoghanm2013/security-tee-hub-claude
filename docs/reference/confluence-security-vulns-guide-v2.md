# Security Vulnerabilities: A Short Guide (v2)

> **Revision:** March 2026  
> **Previous version:** [Original (Q1 2024)](https://datadoghq.atlassian.net/wiki/spaces/TS/pages/3380642367)  
> **Audience:** TSEs working Security tickets  
> **Author:** TEE team

---

## What Are They?

You're a TSE. A customer opens a ticket with a screenshot of CVEs, asks about auto-closing timelines, or wants to know why a vulnerability keeps reappearing after a library upgrade. This guide gives you the foundations.

Datadog has **two distinct product areas** that detect vulnerabilities:

| Product | What it scans | How it collects | Where it lives in-app |
|---|---|---|---|
| **Cloud Security Vulnerabilities** (formerly Infrastructure Vulnerabilities / CSM VM) | OS packages and app packages on hosts, host images, container images, serverless functions | Datadog Agent (SBOM collection) or Agentless Scanning (cloud API-based snapshots) or CI/CD scanning | Security > Cloud Security Management > Vulnerabilities |
| **Software Composition Analysis (SCA)** (formerly Application Vulnerability Management / AVM OSS) | Open-source libraries in application dependencies | Runtime: Datadog Tracer (APM telemetry). Static: repo/CI scanning via GitHub integration or `datadog-ci` | Security > Code Security > Vulnerabilities Explorer |

Additionally, **Code Security (IAST)** detects vulnerabilities in first-party code by tracing tainted data at runtime, and **SAST** scans source code statically. Both surface findings in the same Code Security Vulnerabilities Explorer.

---

## What (are they defined as?)

A vulnerability is any weakness inside a system or application that can be exploited by a threat actor.

### Cloud Security Vulnerabilities

Cloud Security Vulnerabilities (sometimes still referred to as CSM VM) continuously scans infrastructure for known vulnerabilities across:

- **Hosts** (OS packages)
- **Host images** (AMIs, etc.)
- **Container images** (OS packages + application packages, mapped to image layers)
- **Serverless functions** (Lambda, ECS Fargate, Azure Container Apps/Instances, GCP Cloud Run)
- **Container registries** (ECR running + at-rest, Google Artifact Registry, Azure Container Registry)

It works by collecting a Software Bill of Materials (SBOM), which is a full inventory of every package in the scanned resource. The SBOM itself does not create vulnerabilities; the backend matches SBOM contents against a database of known CVEs.

**Key capabilities (current):**
- Risk-based prioritization using the **Datadog Severity Score** (combines CVSS base score with EPSS, CISA KEV, exploit availability, and runtime context like production exposure, sensitive data, and attack activity)
- **Guided remediation** with layer-level vulnerability mapping for container images
- **Infrastructure Packages Catalog**: real-time inventory of all packages across hosts and container images, searchable by package version to assess impact of emerging CVEs
- **SBOM export via API** (preview)
- **Jira integration and automation pipelines** for SLA-based remediation workflows
- Reporting via out-of-the-box dashboards

### Software Composition Analysis (SCA)

SCA replaced Application Vulnerability Management (AVM) in 2024. Existing AVM customers were migrated transparently. SCA tracks and analyzes open-source libraries across the entire SDLC:

**Two complementary detection modes:**

1. **Runtime SCA** - The Datadog Tracer detects libraries loaded in memory when the application starts. This reports the exact libraries and versions running right now, regardless of what the source code says. Enabled via APM telemetry (`DD_INSTRUMENTATION_TELEMETRY_ENABLED=true`, which is on by default).

2. **Static SCA** - Scans dependency manifests and lockfiles in repositories. Runs automatically on commits to enabled repos (via GitHub integration) or in CI/CD pipelines. Also supports Azure DevOps, GitLab, and other providers via `datadog-ci`.

**Key capabilities (current):**
- **Vulnerability Explorer**: live view continuously matched against the latest advisory database. New CVEs appear automatically without re-scanning.
- **Repositories Explorer**: point-in-time snapshot of libraries and vulns at a specific commit.
- **Library Inventory**: full inventory of all third-party libraries (vulnerable or not) across repos and runtime.
- **PR Gates**: block risky PRs before merge based on severity thresholds or license violations.
- **Retroactive advisory matching**: when Datadog ingests a new advisory, it matches against your stored library inventory. No re-scan needed.
- **Datadog Severity Score**: same scoring system as Cloud Security Vulnerabilities, incorporating CVSS + EPSS + exploit availability + runtime context + reachability analysis.

**Vulnerability database:** Datadog SCA uses a curated proprietary database sourced from OSV, NVD, GitHub advisories, and language ecosystem advisories, plus Datadog Security Research team findings (including the [GuardDog](https://github.com/DataDog/guarddog) project for malware detection). New advisories typically appear within minutes, with a maximum of 2 hours.

### Code Security (IAST)

Interactive Application Security Testing detects vulnerabilities in first-party code by tracking data flow through the application at runtime. It monitors tainted data from entry (sources) to operations (sinks) to detect injection vulnerabilities. Enabled via `DD_IAST_ENABLED=true`. This is a separate SKU from SCA.

### SAST

Static Application Security Testing scans first-party source code for vulnerabilities (SQL injection, hardcoded credentials, OWASP Top 10) without executing the code. Runs in CI/CD or via Datadog-hosted scanning.

---

## Who (owns them?)

### Cloud Security Vulnerabilities

Owned by the **Cloud Security Management** team. The vulnerability lifecycle and storage layer is shared with the Code Security team.

**Support channel:** `#support-cloud-security`

### SCA / Code Security (IAST + SAST)

Owned by the **Code Security** team (this evolved from the ASM team post-Sqreen acquisition). SCA, IAST, and SAST are three independent SKUs under the Code Security umbrella.

**Support channel:** `#support-code-security`

> **Note on packaging:** As of 2024, the Datadog Application Security portfolio consists of three independent products:
> 1. **SCA** (GA) - open-source library vulnerabilities
> 2. **Application and API Protection / AAP** (GA) - threat detection (formerly ASM Threat Management)
> 3. **Code Security** (GA) - first-party code vulnerabilities (IAST + SAST)
>
> *Confirmed via the SCA & Code Security wiki (page 3779723986), updated through 2025.*

---

## Where (are they collected from, and displayed?)

### Cloud Security Vulnerabilities

**Collection:**
- **Agent-based:** The agent collects SBOMs from hosts and container images. On containerized hosts, the `sbom` check collects from the container runtime (containerd). Image metadata is collected via the `container_images` check. For container images, the agent uses a workloadmeta collector that subscribes to the runtime socket.
- **Agentless Scanning:** Cloud-provider APIs and ephemeral scanner infrastructure snapshot volumes and analyze them offline. No agent installation required. Currently GA on AWS, preview on Azure, and public beta on GCP (as of Q4 2025).
  - EC2/VM: root volumes are snapshotted and analyzed
  - Container images: scanned from registries (ECR, Artifact Registry, ACR)
  - Serverless: Lambda layers, ECS Fargate tasks, Cloud Run services
- **CI/CD scanning:** Container images can be scanned in CI pipelines before deployment.

**Display locations:**
- **Security > Cloud Security Management > Vulnerabilities** (primary findings page)
- **Infrastructure > Containers > Container Images** (container image vulns with layer mapping)
- **Infrastructure List > Hosts > Security tab** (host-specific vulns)
- **Infrastructure Packages Catalog** (real-time package inventory)

### SCA / Code Security

**Collection:**
- **Runtime:** APM telemetry events containing libraries detected by the tracer at application start. Consumed by `vulnerability-detector-reducer` service in the backend.
- **Static:** GitHub integration (webhook on commits), `datadog-ci` for other SCMs, or Datadog-hosted scanning.

**Display locations:**
- **Security > Code Security > Vulnerabilities Explorer** (live vulnerability view for enrolled services)
- **Security > Code Security > Repositories Explorer** (per-commit scan results)
- **Security > Code Security > Library Inventory** (full library catalog)
- **APM > Service Catalog > Security view** (free for APM users, shows all vulns for all services/envs, live data only, base info)

---

## When (are they collected? / Vulnerability Lifecycle)

### Cloud Security Vulnerabilities

Every **20 minutes**, the product checks whether a vulnerability should be auto-closed.

| Vulnerability Type | Auto-Close Condition |
|---|---|
| **Host** | Not seen for more than **27 hours**, OR host terminated within **1 hour** |
| **Host Image** | Not seen for more than **27 hours** |
| **Container Image (agent-based)** | Not seen for more than **3 hours** |
| **Container Image (agentless)** | Not seen for more than **27 hours** |

**Additional closure logic for container images:**
- If a newer image instance has been first seen more than 30 minutes ago and does NOT contain the vulnerability, the vuln is closed (i.e., image was "fixed" by updating).
- Example: `alpine:1` is vulnerable to A and B. `alpine:2` arrives with only B. Vulnerability A is closed.

**Deletion:** Image vulnerabilities are deleted after not being seen for **30 days**. Host vulnerabilities are deleted after not being seen for **1 day**.

> **Confidence level:** The 27-hour / 3-hour / 30-day timings are confirmed across the CSM VM wiki (page 4070573198, updated March 2025) and the Agentless Scanning guide (page 6091735214, updated January 2026). The original page had 15 hours for host images, which the current sources have updated to 27 hours.

### SCA (Runtime)

SCA uses a **Hot/Lazy/Cold dependency model** for auto-close:

| Dependency Type | Definition | Auto-Close Condition |
|---|---|---|
| **Hot** | Libraries from services alive for >2 hours | Not detected for more than **1 day**, AND service is running on all environments where the vuln was detected |
| **Lazy** | Libraries loaded >1 hour after service start | Not detected for more than **5 days** |
| **Cold** | Libraries from short-lived services (<2 hours, e.g. jobs) | Not detected for more than **5 days** |

**Additional SCA closure logic:**
- If status is REMEDIATED and not detected for **2 hours**, transition to auto-closed.
- For hot dependencies: if not detected for more than **1 hour** and other vulnerabilities ARE detected for the same service on the same environments, it's closed (the service restarted with a fixed dependency).

> **Confidence level:** These timings are confirmed in the public docs (docs.datadoghq.com/security/code_security/software_composition_analysis/) and the SCA wiki (page 3779723986). The original page listed SCA auto-close at "5 days" universally and IAST at "18 months". Both have changed.

### Code Security (IAST)

| Condition | Auto-Close |
|---|---|
| Not seen for more than **14 days** | Auto-closed |
| Not seen for more than **24 hours** AND not detected in active service versions (requires version tag) | Auto-closed |

> **Confidence level:** The Agentless Scanning guide (page 6091735214) lists IAST at 14 days / 24 hours with version tag. The original page listed 18 months, which is outdated.

### SAST / Secrets / IaC (Static Code Security)

| Condition | Auto-Close |
|---|---|
| Not seen for more than **3 hours** AND not detected in the latest scanned commit | Auto-closed |

### SCA (Static)

| Condition | Auto-Close |
|---|---|
| **3 hours** after advisory removed/excluded, OR immediately after a commit that removes the vulnerable library version | Auto-closed |

### Agentless Scanning Frequency

| Scan Type | Frequency |
|---|---|
| CSPM / CIEM (API-based) | ~15 minutes |
| VM & image vulnerabilities | Every **12 hours** (not customizable currently) |

> **Note:** Agentless scanning is batch-based, not event-driven. New packages installed on a VM will not be detected until the next scan cycle.

---

## Why (are they important?)

### Cloud Security Vulnerabilities

Security practitioners and compliance teams need continuous visibility into infrastructure vulnerabilities for:
- **Compliance audits** (SOC2, PCI, HIPAA, CIS, FedRAMP)
- **Emerging vulnerability response** (0-day CVEs)
- **Vulnerability management programs** spanning CI/CD to production

### SCA / Code Security

Development and DevSecOps teams need visibility into application-level risk:
- Open-source libraries accelerate development but expand the **attack surface**
- Runtime detection shows what's actually running in production, not just what's in the source code
- Static detection catches vulnerabilities before they reach production
- **PR Gates** shift security left by blocking risky changes before merge

*attack vector: a method of gaining unauthorized access to a system to extract data*  
*attack surface: the total number of possible attack vectors an attacker can use*

---

## How (are they collected?)

### Cloud Security Vulnerabilities

**INTERNAL NOTE:** Customers should NOT be told that Datadog uses Trivy for scanning. This is not designed to be public knowledge. If a customer has concerns about vulnerability data accuracy (wrong version, remediation steps not reflected), engage `#support-cloud-security` before replying.

**Agent-based pipeline:**
1. Image metadata collected by `container_images` check, sent to Container Images track
2. SBOMs collected by `sbom` check, scanned using Trivy, sent to SBOM track
3. Backend matches SBOM contents against known vulnerability database
4. Vulnerabilities attached to container images / hosts and surfaced in CSM

**Agentless pipeline:**
1. Cloud account onboarded with IAM role (read permissions)
2. Ephemeral scanner instances deployed in customer's cloud (via CloudFormation/Terraform)
3. Root volumes snapshotted, container images pulled from registries
4. Filesystem/image contents analyzed offline
5. Findings sent to Datadog and surfaced in CSM

**Key points for troubleshooting the agent-based path:**
1. Exporting the image through the runtime socket (containerd)
2. Scanning the image with Trivy
3. Sending SBOMs to Event Platform (check: is the agent check scheduled? are SBOMs being sent periodically?)
4. Processing the SBOM in the backend (check: are SBOM payload fields correctly set?)

### SCA (Runtime)

1. Tracer starts with the application
2. Tracer collects libraries loaded in memory via runtime instrumentation API
3. Library list sent to Datadog via APM telemetry (`apmtelemetry` track)
4. `vulnerability-detector-reducer` matches libraries against advisory database
5. `vulnerability-reducer` deduplicates, adjusts severity via RAP service, stores in REDAPL

**Important:** Runtime SCA reports the exact libraries and versions running in the service, regardless of what the source code says. Disconnections between source and runtime can come from:
- Build systems replacing library versions
- Unpatched code left running in production
- Language runtimes replacing library versions (e.g. NuGet)

### SCA (Static)

1. Commit triggers webhook (GitHub) or CI pipeline runs `datadog-ci`
2. Dependency manifests/lockfiles are analyzed
3. SBOM generated and sent to Datadog (`cideps` track in EVP)
4. Vulnerability Management Engine processes SBOM and surfaces vulnerabilities
5. New advisories published after the scan are retroactively matched against stored inventory

---

## Vulnerability Statuses

Any vulnerability can have the following status:

| Status | Meaning |
|---|---|
| **Open** | At least one active asset instance has this vulnerability |
| **Auto-Closed** | No active asset instances with this vulnerability (closed by lifecycle logic) |
| **Muted** | Active instances exist, but user changed status to Muted (permanently or for a set duration) |
| **Remediated** | Active instances exist, but user manually marked as Remediated. Can reopen if detected on a separate instance. |
| **In Progress** | Active instances exist, but user manually marked as In Progress |

---

## Common Issues / FAQ

### Enablement

**SCA (Runtime) is not showing vulnerabilities, but everything looks configured correctly.**
Check that `DD_INSTRUMENTATION_TELEMETRY_ENABLED` is not set to `false`. It defaults to `true`, but if someone explicitly disabled it, SCA will not receive library data.

### Auto-Closing

**Why are my infrastructure vulnerabilities automatically closing?**
See the lifecycle section above. Vulns are auto-closed when the affected resource is no longer seen within the expected timeframe. For container images, a newer image version without the vulnerability will also trigger closure.

**Why did an SCA vulnerability close even though the library is still in our code?**
Runtime SCA only tracks libraries that are actually loaded. If the application hasn't restarted recently or the service is short-lived, the hot/lazy/cold dependency model determines closure. Check if the service is alive and the library is actively loaded.

### Billing

**AVM OSS was billed by host, but I can't disable by host. What gives?**
SCA is enabled at the service level (via 1-Click enablement in the configuration page). If a service is distributed across multiple hosts, billing applies to each host the service runs on. You cannot scope it to individual hosts within a service.

**What metrics can I use to monitor CSM VM billing?**
- Agent-based: `datadog.csm.vulnerabilities.host_instance`
- Agentless: `datadog.agentless_scanner.vm.hosts`

### Display

**Why is my service labeled as "in production" when my environment tag says otherwise?**
Production detection is inverted: Datadog detects non-production environments via regex. Everything that does not match the regex is treated as production:

```
^(.*-)?(dev|pdev|dit|alpha|beta|lab|perf|uat|sit|sat|sandbox|pre-prod|preprod|test|develop|development|loadtest|testing|integ|int|integration|stag|stage|staging|stg|tst|ci|qa|qual|accept)\d*(-.*)$
```

The "Resource in Production" check is based on **all environments where the service is deployed**, not just the enrolled environments.

**Can I graph my vulnerabilities on a dashboard?**
Yes. Use `datadog.appsec.vulnerabilities` which is groupable by severity, fix availability, team, env, source, service, and more.

### Windows

**Why don't I see vulnerabilities for my Windows host?**
Windows support currently covers vulnerabilities based on missing KB patches from Microsoft only. Third-party software vulnerabilities are not supported yet (on the roadmap). Cumulative updates can cause false positives because Microsoft doesn't clearly document which KBs are included in cumulative patches.

### Agentless Scanning

**Can the agentless scanning interval (12 hours) be customized?**
Not currently. The team is exploring auto-scaling scanners based on remaining resources to scan, but there is no ETA. Capture the customer's use case and ideal frequency as a Feature Request.

**How long after enabling agentless scanning should I expect findings?**
- IAM role: immediate
- Scanner stack deployed: 5-30 minutes
- First resource discovery: up to ~1 hour
- First vulnerability findings: several hours

---

## Deployment Methods Summary

| Method | Best for | Frequency | Coverage |
|---|---|---|---|
| **Datadog Agent** | Hosts where agent is already deployed | Real-time SBOM collection | OS packages (Linux, Windows). App packages in Agent 7.64+. |
| **Agentless Scanning** | Broad coverage without agent deployment | Every 12 hours | OS packages + app packages, hosts, container images, serverless, registries |
| **CI/CD Scanning** | Catching vulns before production | Per pipeline run | Container images |
| **SCA Runtime** | Application library monitoring | On application start | Open-source libraries loaded in memory |
| **SCA Static** | Shift-left library scanning | On commit or CI run | Dependency manifests and lockfiles |

These methods are complementary. A common setup is Agent where it's already deployed, Agentless for the rest, CI/CD for pre-production gates, and SCA for application-level visibility.

---

## What Changed Since the Original Guide (Q1 2024)

| Area | Q1 2024 (Original) | Current (March 2026) |
|---|---|---|
| **Product naming** | "Application Vulnerability Management (AVM)" and "Infrastructure Vulnerabilities" | **SCA** (GA) and **Cloud Security Vulnerabilities** |
| **AVM to SCA transition** | Listed as "Coming Soon" | Fully shipped and GA since 2024. AVM customers auto-migrated. |
| **SCA static scanning** | Described as "Beta" | GA. Supports GitHub, Azure DevOps, GitLab, and other SCMs. |
| **Agentless Scanning** | Not mentioned | GA on AWS, preview on Azure, public beta on GCP |
| **CI/CD scanning** | Not mentioned | Available for container images |
| **IAST auto-close** | 18 months | **14 days** (or 24h with version tag logic) |
| **SCA auto-close** | 5 days universally | Hot/Lazy/Cold model (1 day / 5 days / 5 days) |
| **Host image auto-close** | 15 hours | **27 hours** |
| **Serverless scanning** | Not mentioned | Lambda, ECS Fargate, Cloud Run, Azure Container Apps/Instances |
| **Severity scoring** | Not mentioned | Datadog Severity Score (CVSS + EPSS + CISA KEV + runtime context) |
| **PR Gates** | Not mentioned | GA. Block risky PRs based on severity or license violations. |
| **Retroactive advisory matching** | Not mentioned | New CVEs matched against stored inventory without re-scanning |
| **Infrastructure Packages Catalog** | Not mentioned | Real-time package inventory across all infra |
| **Agent app library scanning** | Not mentioned | Available in Agent 7.64+ |
| **Windows support** | Not mentioned | Supported (KB-based OS vulns; third-party on roadmap) |
| **Container image layer mapping** | Not mentioned | Trace vulns to specific image layers |
| **ASM portfolio** | Single product | Three independent SKUs: SCA, AAP, Code Security |

---

## Confidence Notes

Where I could verify information against current internal wikis or public docs, I have done so. Items marked with "unsure" below may need verification with the owning team:

- **Host vulnerability deletion after 1 day**: confirmed in the original page and the SCA wiki. The Agentless guide doesn't explicitly mention deletion timelines (only auto-close). I kept it but would recommend confirming with `#support-cloud-security`.
- **Container image deletion after 30 days**: confirmed in the original page's FAQ section and the SCA wiki.
- **"vulnerability-detector-reducer" and "vulnerability-reducer" service names**: taken from the original page and the SCA wiki. These internal service names may have changed. Unsure if they are still current.
- **Trivy usage**: still referenced in the CSM VM wiki (page 4070573198) and the SBOM collection page. The internal-only guidance about not sharing this with customers remains in effect.
- **Agentless 12-hour scan interval**: confirmed in the Agentless Scanning guide and the CSM VM wiki.

---

## Reference

- [Cloud Security Vulnerabilities (public docs)](https://docs.datadoghq.com/security/cloud_security_management/vulnerabilities/)
- [Software Composition Analysis (public docs)](https://docs.datadoghq.com/security/code_security/software_composition_analysis/)
- [Cloud Security Vulnerabilities - TS Wiki](https://datadoghq.atlassian.net/wiki/spaces/TS/pages/4070573198)
- [SCA and Code Security - TS Wiki](https://datadoghq.atlassian.net/wiki/spaces/TS/pages/3779723986)
- [Agentless Scanning Support Guide](https://datadoghq.atlassian.net/wiki/spaces/TS/pages/6091735214)
- [SBOM Collection of Container Image](https://datadoghq.atlassian.net/wiki/spaces/TS/pages/3249702351)
- [Hosts and Containers Compatibility](https://docs.datadoghq.com/security/cloud_security_management/vulnerabilities/hosts_containers_compatibility/)
