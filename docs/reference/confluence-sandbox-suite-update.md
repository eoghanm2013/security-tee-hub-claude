# Security Sandbox Suite

Full-suite Datadog Security product testing environment for Technical Escalation Engineers. Run locally with Docker Compose, extend to AWS for cloud-only products.

**Status:** Local stack (AAP, IAST, SCA, CWS, Cloud SIEM) is fully functional. AWS-based modules (CSPM, CIEM, VM) are in progress.

**Repo:** https://github.com/eoghanm2013/security-sandbox-suite

---

## What's Covered

| Product | Local | AWS | How |
|---------|-------|-----|-----|
| **AAP** (App & API Protection) | Yes | - | 4 vulnerable web apps with `DD_APPSEC_ENABLED` |
| **IAST** | Yes | - | Same apps with `DD_IAST_ENABLED`, tainted data flows |
| **SCA** | Yes | - | Pinned vulnerable deps, `DD_APPSEC_SCA_ENABLED` |
| **SAST** | Yes | - | App source code has intentional vulns (scan target) |
| **CWS** (Workload Protection) | Yes | - | Agent with system-probe, trigger scripts |
| **Cloud SIEM** | Yes | Yes | Synthetic CloudTrail + Okta events trigger OOTB detection rules |
| **CSPM** | - | Yes | Intentionally misconfigured S3, SG, EBS |
| **CIEM** | - | Yes | Over-permissioned IAM roles, cross-account access |
| **VM** (Vulnerabilities) | - | Yes | EC2 with vulnerable packages, ECR with vuln images |

---

## Prerequisites

| Requirement | How to verify | Notes |
|-------------|--------------|-------|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | `docker info` | Must be open and running, not just installed |
| [Git](https://git-scm.com/) | `git --version` | |
| Datadog API Key | [Get one here](https://app.datadoghq.com/organization-settings/api-keys) | Required. App Key is optional. |
| Python 3 (optional) | `python3 --version` | Only needed for the SIEM event generator |
| [Terraform](https://developer.hashicorp.com/terraform/install) (optional) | `terraform --version` | Only for AWS cloud modules |

If you only want to test a specific product, check the `playbooks/` folder for per-product guides.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/eoghanm2013/security-sandbox-suite.git
cd security-sandbox-suite

# 2. Run the interactive setup (creates .env, asks for API key and products)
./scripts/up.sh
```

The startup script will:
1. Create `.env` and ask for your `DD_API_KEY` (first run only)
2. Show a product menu where you pick what to test
3. Optionally start traffic generators
4. Launch only the containers you need

To skip the menu and start everything: `./scripts/up.sh --all`

### Product selection menu

```
Which products do you want to test?

  [1] AAP   - App & API Protection (WAF, attack detection)
  [2] IAST  - Tainted data flow analysis
  [3] SCA   - Vulnerable dependency scanning
  [4] SAST  - Static code analysis (apps as scan target)
  [5] CWS   - Workload Protection (eBPF runtime security)
  [6] SIEM  - Cloud SIEM (OOTB detection rules)
  [7] All

Enter choices (comma-separated, e.g. 1,2,5):
```

Only the selected products' containers and features start. For example, selecting `5,6` (CWS + SIEM) launches only the Datadog Agent and the SIEM generator, with no web apps, database, or proxy.

---

## Architecture

```
localhost:8080 (nginx gateway)
  /py/   -> python-app:8001   (Flask + dd-trace-py)
  /node/ -> node-app:8002     (Express + dd-trace-js)
  /java/ -> java-app:8003     (Spring Boot + dd-java-agent)
  /php/  -> php-app:8004      (Slim + dd-trace-php)

postgres:5432  - Shared database (pre-seeded pet shop data)
redis:6379     - Session store
dd-agent:8126  - Datadog Agent (APM + Logs + CWS + Process + SBOM + Compliance)
```

---

## Vulnerable App: Bits & Bytes Pet Shop

Each language implements the same pet supply store with identical vulnerability surfaces:

| Endpoint | Vulnerability | Tests |
|----------|--------------|-------|
| `GET /search?q=` | SQL Injection | AAP WAF, IAST |
| `POST /login` | SQLi + Broken Auth | AAP, IAST |
| `GET /product/:id` | SQLi (numeric) | AAP, IAST |
| `POST /review` | Stored XSS | AAP WAF |
| `GET /profile/:user` | Reflected XSS | AAP WAF |
| `POST /upload` | Path Traversal | AAP, IAST |
| `POST /webhook` | SSRF | AAP, IAST |
| `GET /export?file=` | Command Injection | AAP, IAST |
| `POST /cart/restore` | Insecure Deserialization | IAST |

---

## Cloud SIEM

The SIEM event generator produces synthetic logs in the native format of real integrations (AWS CloudTrail + Okta). The Datadog Agent collects them with the correct `source` tag, which activates built-in log pipelines. OOTB detection rules fire automatically, producing real Security Signals with zero custom rule setup.

Select option `6` during startup, or start manually:

```bash
docker compose --profile siem up -d siem-generator
```

10 OOTB rules are targeted:

| Integration | Rule |
|-------------|------|
| CloudTrail | AWS CloudTrail configuration modified |
| CloudTrail | AWS GuardDuty detector deleted |
| CloudTrail | AWS IAM AdministratorAccess policy applied to user |
| CloudTrail | AWS EBS Snapshot Made Public |
| CloudTrail | AWS KMS key deleted or scheduled for deletion |
| CloudTrail | AWS CloudWatch log group deleted |
| Okta | Okta API Token Created or Enabled |
| Okta | Okta administrator role assigned to user |
| Okta | Okta MFA reset for user |
| Okta | Okta policy rule deleted |

Some events trigger additional rules too (e.g. `AttachUserPolicy` also fires "AWS IAM policy modified").

Signals appear in **Security > Cloud SIEM > Signals** within 2-5 minutes. Filter by `env:sandbox`.

---

## Scripts

| Script | What it does |
|--------|-------------|
| `scripts/up.sh` | Interactive startup (pick products, configure .env, launch) |
| `scripts/up.sh --all` | Start everything, no prompts |
| `scripts/down.sh` | Stop everything |
| `scripts/traffic.sh start [profile]` | Start traffic (all/normal/attacks/iast) |
| `scripts/traffic.sh stop` | Stop traffic generators |
| `scripts/aws-deploy.sh` | Deploy AWS resources (Terraform) |
| `scripts/aws-destroy.sh` | Tear down AWS resources |

---

## Cleanup

```bash
# Stop all containers
./scripts/down.sh

# Stop and remove volumes (database data, SIEM logs)
./scripts/down.sh -v

# Full cleanup: containers, volumes, and built images
./scripts/down.sh -v --rmi local
```

---

## AWS (On-Demand)

Cloud-only products use Terraform in `terraform/aws/`. All resources are tagged per sandbox policy.

```bash
./scripts/aws-deploy.sh    # Plan + apply
./scripts/aws-destroy.sh   # Destroy when done
```

---

## Playbooks

Per-product guides in `playbooks/`:

| Playbook | Product | Local/AWS |
|----------|---------|-----------|
| `aap.md` | App & API Protection | Local |
| `iast.md` | IAST | Local |
| `sca.md` | SCA | Local |
| `sast.md` | SAST | Local |
| `cws.md` | Workload Protection | Local |
| `siem.md` | Cloud SIEM | Local + AWS |
| `cspm.md` | Cloud Misconfigurations | AWS |
| `ciem.md` | Identity Risk Management | AWS |
| `vm.md` | Vulnerability Management | AWS |

Each covers what the sandbox tests, how to verify it's working, and common escalation patterns you can reproduce.
