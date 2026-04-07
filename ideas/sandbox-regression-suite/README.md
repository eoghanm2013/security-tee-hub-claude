# Sandbox Regression Suite

**Status:** Concept
**Effort:** High
**Impact:** High (shifts from reactive to proactive)

## Problem

The sandbox suite is currently reactive: spin it up when a customer reports an issue, reproduce the problem, tear it down. But it's a fully instrumented, multi-language environment with intentional vulnerabilities and realistic traffic generation. That's 90% of what you need for a continuous validation system.

## Idea

Run the sandbox on a schedule (CI, cron, or a lightweight orchestrator) and validate that Datadog's security products detect what they're supposed to. Essentially an internal regression suite for security product correctness.

### What it would validate

| Product | Expected Detection | How to verify |
|---------|-------------------|---------------|
| AAP | SQL injection, XSS in traffic scenarios | Check for security signals in Datadog after traffic run |
| SCA | Known CVEs in intentionally vulnerable deps | Check vulnerability findings via API |
| IAST | Tainted data paths through app code | Check IAST findings via API |
| SAST | Hardcoded credentials in source code | Check SAST findings via API |
| CWS | Malicious process execution from trigger scripts | Check CWS signals |
| SIEM | Detection rules firing on generated events | Check SIEM signals |
| CSPM | Misconfigured cloud resources (Terraform) | Check CSPM findings |

### What this catches

- A tracer update breaks AppSec detection for PHP -- you know before customers report it
- A rule update causes false negatives in CWS -- caught in the next scheduled run
- An agent version bump changes SBOM behavior -- regression test fails, triggers investigation

### Architecture sketch

```
Schedule (daily or on agent/tracer release)
  |
  v
Spin up sandbox suite (docker compose up)
  |
  v
Run traffic scenarios (k6 normal + attacks + IAST)
Run CWS trigger scripts
Run SIEM event generator
  |
  v
Wait for processing (5-10 min)
  |
  v
Query Datadog APIs for expected signals/findings
  |
  v
Compare against expected baseline
  |
  v
Report: PASS / FAIL (with details on what's missing)
  |
  v
Tear down
```

## What exists already

The [Security Sandbox Suite](https://github.com/eoghanm2013/security-sandbox-suite) (now its own repo) provides:

- 4 vulnerable web apps with Docker Compose, traffic generation, CWS triggers, SIEM events
- k6 scenarios for normal, attack, and IAST traffic
- Custom CWS rules and trigger scripts
- SIEM event generator
- Terraform modules for cloud-side products (CSPM, CIEM, VM, SIEM)

## What's missing

- A test harness that queries Datadog APIs for expected signals after a run
- An expected-results baseline to compare against
- CI/scheduling integration (GitHub Actions, or a cron job in the sandbox account)
- Notification on failure (Slack, PagerDuty, or just a JIRA ticket)

## Open questions

- Where does this run? Sandbox AWS account? GitHub Actions? Local cron?
- How do you handle flaky detections (timing-dependent signals)?
- Should it pin agent/tracer versions and test against nightly builds?
- Who owns the baseline? Does it auto-update when new products/rules are added?
- Could this be useful to the product engineering teams as an integration test?
