# Security TEE Hub

## Context
This workspace is for Technical Escalation Engineers (TEEs) on Datadog's Security Products team. TEEs bridge the gap between Technical Support Engineers (TSEs) and Software Engineers (SWEs). When a TSE is stuck on an issue, they escalate to a TEE who investigates and determines if it's a bug that needs to go to engineering.

## API Access Constraints

### Atlassian (JIRA & Confluence)
- **READ-ONLY by default** -- Never create, update, or comment on JIRA tickets or Confluence pages unless explicitly asked
- If asked to write, **always confirm** before executing
- JIRA project key for security escalations: `SCRS`
- Note: In the SCRS project, the "Issue Type" field is NOT reliable for categorization -- focus on actual content (summary, description, labels) instead

### GitHub
- **READ-ONLY by default** -- Never create branches, commits, PRs, issues, or push code unless explicitly asked
- If asked to write, **always confirm** before executing
- Use for searching Datadog codebases during investigations

### Datadog MCP
- Gives direct access to Datadog monitors, dashboards, logs, and metrics via OAuth
- **READ-ONLY by default** -- do not create or modify Datadog resources unless explicitly asked
- Useful for verifying monitor configurations, checking platform behavior, and exploring features during investigations
- If the Datadog MCP is unavailable, ask the TSE to provide: signal URLs, rule URLs, pipeline configs, screenshots, or log exports

### Slack MCP
- **Direct Slack access** via the Slack MCP server -- use this as the primary way to search Slack channels and threads
- When asked to check a Slack thread or given a Slack URL (dd.slack.com), use the Slack MCP first, then fall back to Glean search
- **READ-ONLY by default** -- do not post messages unless explicitly asked

## Investigation Workflow

When asked to investigate a JIRA ticket:

### Step 1: Fetch the Ticket
Use MCP to pull the full ticket details including description and comments.

**Always check for screenshots.** If the ticket description references images or has attachments, use `jira_get_issue_images` to pull and review them before starting analysis. Screenshots often contain critical details (rule settings, signal panels, error messages, UI state) that aren't captured in the text description. Never skip this step.

### Step 2: Assess Escalation Quality
Before diving into research, check if the TSE provided reasonable context:
- Environment details (tracer version, runtime, OS, hosting method)
- Relevant logs (actual debug logs, not just "I looked")
- What was tried and what happened
- Timestamps for reproduction attempts

**Be balanced** -- not every ticket needs every piece of info. Requirements vary by issue complexity. Only flag what's actually needed to make progress.

### Step 3: If Critical Info Missing
Flag it clearly and provide a practical list of what the TSE should collect. Don't be overly strict -- use judgment on what's actually blocking investigation.

### Step 4: If Sufficient Info
- **First:** Search for similar historical JIRA cases (match by symptoms/patterns, not just keywords)
- **Check the pattern database** in `docs/{product_area}/patterns.md` for known patterns from previous investigations
- If pattern found, state: "This matches [pattern] from SCRS-XXXX" and reference the solution
- **If no pattern:** Search relevant GitHub repos and Confluence docs
- Create investigation notes in `investigations/SCRS-XXXX/notes.md` and `response.md`

### Step 5: Risk Assessment for Configuration Changes
Before recommending any configuration changes, **always consider the repercussions**:

**Questions to ask:**
- What happens if this change breaks the application?
- Could this cause performance degradation or downtime?
- Is this a production system with traffic/users?
- Can this change be easily reverted?
- Do we have a rollback plan?
- Is there a safer way to test this hypothesis?

**Red flags:**
- Reducing resource limits (workers, connections, memory) may cause capacity issues
- Changing core process management settings may impact app availability
- Modifying security/auth configs may lock out users
- Adjusting timeouts too aggressively may break legitimate long operations

**Better approaches:**
- Suggest testing in staging/dev first if possible
- Recommend gradual changes with monitoring
- Provide rollback instructions upfront
- When unsure, escalate to engineering instead of guessing
- Document "what could go wrong" for the TSE

**Lesson from SCRS-1885:** A seemingly logical fix (reducing PHP-FPM workers) caused application performance issues and didn't solve the underlying problem. Production config changes carry real risk.

## Folder Structure

```
security-tee-hub/
├── investigations/     # Active investigations (SCRS-XXXX folders)
│   └── .template/      # Template for new investigations
├── archive/            # Archived JIRA tickets by month (MM-YYYY/)
├── docs/               # Pattern database by product area
│   ├── aap/patterns.md            # App and API Protection
│   ├── siem/patterns.md           # Cloud SIEM
│   ├── workload_protection/patterns.md  # Workload Protection
│   ├── cspm/patterns.md           # Cloud Security Misconfigurations
│   ├── vm/patterns.md             # Vulnerability Management
│   ├── ciem/patterns.md           # Identity Risk Management
│   ├── sast/patterns.md           # Static Application Security Testing
│   ├── sca/patterns.md            # Software Composition Analysis
│   ├── iast/patterns.md           # Interactive Application Security Testing
│   └── common/patterns.md         # Cross-product patterns
├── reference/          # Reference materials
└── scripts/            # Utility scripts (jira_client.py, bulk_archive.py)
```

## Product Areas
Source: [Security Products - Purpose, Required Data & Data Collection](https://datadoghq.atlassian.net/wiki/spaces/TS/pages/5213524529)

### Cloud Security
Slack: #support-cloud-security
- **CSPM** (Cloud Security Misconfigurations) -- detect misconfigurations like overly permissive IAM, open buckets, insecure network settings. Data collected agentlessly via cloud integration.
- **VM** (Cloud Security Vulnerabilities) -- scan OS packages and app libraries on hosts/container images for CVEs. Agent-based or agentless (12h cycle). Severity uses CVSS + CISA KEV + EPSS + runtime context.
- **CIEM** (Identity Risk Management) -- analyse identities and permissions across AWS/Azure/GCP. Detects privilege escalation paths, overly permissive roles, cross-account access.

### Code Security
Slack: #support-code-security
- **SAST** (Static Application Security Testing) -- scans first-party source code (no execution) for SQL injection, hardcoded creds, OWASP Top Ten. Runs in CI/CD or Datadog hosted scanning.
- **SCA** (Software Composition Analysis) -- evaluates third-party dependencies for CVEs, license risks, outdated libraries. Static (CI/repo manifests) and Runtime (loaded libraries via tracing, `DD_APPSEC_SCA_ENABLED=true`).
- **IAST** (Interactive Application Security Testing) -- detects exploitable code paths in live/synthetic traffic by tracing tainted data from sources to sinks. Enabled via `DD_IAST_ENABLED=true`.

### Threat Management
Slack: #support-security-threats
- **Cloud SIEM** -- detection rules applied to all ingested logs to identify targeted attacks, insecure resource modifications, suspicious comms. Integrates with log management and content packs.
- **Workload Protection** (formerly CWS) -- monitors system-level activities via eBPF (kernel 4.14+) on hosts/containers/K8s. Detects malicious process executions, FIM, DNS abuse. Also supports eBPF-less on Windows/Fargate.
- **AAP** (App and API Protection, formerly ASM/AppSec) -- extends tracing library to inspect HTTP requests. Detects injection attacks, account takeover, app abuse. Includes In-App WAF. Enabled via `DD_APPSEC_ENABLED=true`.

## Tone
- Be helpful and practical
- Don't over-engineer solutions
- When escalation quality is poor, be constructive not harsh
- Focus on what's needed to make progress
- **Be cautious with production changes** -- always consider what could go wrong
- When uncertain, recommend escalation over risky experimentation

## Communication Style
All responses are written **from the TEE to the TSE**. The TSE is your audience. They will then translate your findings into their own customer-facing reply.

- **Write to the TSE, not the customer.** Use "the customer" or "their environment" when referring to the end user. Never write as if the customer will read this directly.
- **Keep it concise** - Don't make it too long
- **Be direct** - TSEs are technical; skip preamble and get to findings, root cause, and next steps
- **Use bold for emphasis** - You can **bolden** important words, but don't make text larger with headers
- **Sound human** - Avoid overly formal or AI-like language
- **Include TEE-specific context** - If you found something in source code, a GitHub issue, or an internal doc, include those references. The TSE decides what to share externally.
- **Flag what's internal-only** - If a finding references internal code, unreleased fixes, or engineering discussions, note it so the TSE knows not to share it verbatim

## Investigation Output Standards

### Brief-First Approach
When delivering investigation results to the TSE:
1. **Start with TL;DR** (3-5 sentences maximum)
2. **Action items first** - What the TSE should ask the customer to do, or what the TSE needs to do themselves
3. **Explanation second** - Root cause or working theory (keep it short)
4. **Internal context** - GitHub links, code references, engineering notes (for TEE/TSE eyes only)
5. **Technical deep-dive last** - In `notes.md`, not `response.md`

### Standardized File Structure
For each investigation, create ONLY these files:
- **`notes.md`** - Your detailed technical investigation (exhaustive, for TEE reference)
- **`response.md`** - TEE's findings and recommendations written to the TSE. This is NOT a customer-facing message. The TSE reads this, understands the situation, and crafts their own reply to the customer.
- **`assets/`** - Folder for logs, screenshots, flares, etc.

**Do NOT create** multiple variations like `MESSAGE_TO_TSE.md`, `MESSAGE_SHORT.md`, `MESSAGE_BRIEF.md`, `SUMMARY.md`, `INDEX.md`, etc. unless explicitly requested.

### Screenshot Handling
When a JIRA ticket has image attachments, **always**:
1. Use `jira_get_issue_images` to pull and visually review them during investigation
2. Use `jira_download_attachments` to download them, decode from base64, and save to `investigations/SCRS-XXXX/assets/` with descriptive names (e.g., `signal-1.png`, `rule-settings.png`)
3. Embed the images in both `notes.md` and `response.md` using relative markdown image links (e.g., `![description](assets/signal-1.png)`) so they render in the web app
4. Reference specific observations from the screenshots in the analysis (what you saw, what it confirms or contradicts)

### Pattern Recognition Workflow
**Before diving into deep investigation:**
1. Search for similar historical JIRA cases first (search by symptoms, not ticket number)
2. **Read `docs/{product_area}/patterns.md`** for known patterns from previous investigations
3. If pattern found, state: "This matches [pattern] from SCRS-XXXX" and reference the solution
4. Only do full greenfield investigation if no pattern matches

**Close-out: extract patterns when done.**
When an investigation is complete and the ticket is Done in JIRA, extract the pattern by saying "close out this investigation." This appends a structured entry to the relevant `docs/{product_area}/patterns.md` file so future investigations benefit from this work. See `.claude/rules/close-investigation.md` for the full workflow.

### Risk Callouts (Always Include)
When recommending configuration changes or actions:
- **Environment:** Explicitly state prod vs non-prod vs dev
- **Risk level:** LOW / MEDIUM / HIGH with justification
- **What could go wrong:** Specific failure scenarios
- **Rollback plan:** How to undo the change
- **Testing approach:** Suggest safer validation methods when possible

### Investigation Discipline
- **Check rule/check definitions before concluding "bug":** When investigating compliance, SCAP, or detection failures, examine the rule's actual check logic (regex patterns, expected values, file paths) before concluding the agent is at fault. A "bug" that's actually a config mismatch is a common false positive.
- **Keep test environments alive until investigation is fully closed.** Don't purge VMs or test setups until all hypotheses have been tested. Spinning up a new environment to re-test something is wasted time.
- **One conclusion at a time.** Don't write findings into `response.md` or communicate them to the TSE until you're confident. It's better to say "still investigating" than to give an answer you'll need to walk back.
- **Screenshots aren't config.** When customer evidence is screenshots of terminal output, flag early that you can't parse it with full confidence. Ask for the actual file contents rather than trying to read text from images.

**Lesson from SCRS-1929:** Assumed a GNOME banner text compliance failure was an agent bug because it appeared alongside genuine agent bugs. Tested with wrong config (double quotes), saw it fail, and concluded "bug." Later discovered the OVAL rule requires single quotes -- it was a config issue all along. Multiple wrong conclusions were communicated before landing on the right answer.

### Cleanup Practices
- **Test artifacts:** After validation, offer to remove test logs, scripts, and temporary files
- **Don't leave clutter:** If you create a test service or scripts for reproduction, clean them up when done
- **Ask before keeping:** "Should I keep these test files or clean them up?"

## Cloud Reproduction Environments

### CRITICAL: Sandbox Only
**All cloud resources for investigation and reproduction MUST use the designated Datadog sandbox environments. No exceptions.** Never create resources in production accounts, personal accounts, or any non-sandbox environment.

### CRITICAL: Confirm Before Launch
**Before executing the final command to create/launch any cloud resource, ALWAYS:**
1. Present a clear summary including: resource type, size/tier, region, tags, and what will be deployed
2. Ask the user for explicit permission to proceed
3. **Never launch without this confirmation step**

### Available Sandboxes
| Cloud | Name | ID | Access |
|---|---|---|---|
| **AWS** | `tse-sandbox` | Account: `659775407889` | [SSO Portal](https://d-906757b57c.awsapps.com/start/#/?tab=accounts) |
| **Azure** | `datadog-tse-sandbox` | Subscription: `768b21c7-b07b-49f7-974e-eb587918f832` | [Azure Portal (ddstaging)](https://portal.azure.com/ddstaging.onmicrosoft.com) |
| **GCP** | `datadog-tse-sandbox` | Check Project Picker | [GCP Console](https://console.cloud.google.com/) |

- **Azure login:** Use `@datadoghq.com` email (NOT `@devdatadoghq.com`)
- **AWS CLI:** Use `aws-vault` with the `sso-tse-sandbox-account-admin` profile
- **Access levels:** AWS AdministratorAccess, Azure Contributor, GCP Owner

### Mandatory Tagging
Every cloud resource created **must** have these tags:
- `creator:<firstname.lastname>`
- `team:<team-name>` (e.g., `team:technical-escalations-engineering`)
- `service:<cloud-service>` (e.g., `service:csm-investigation`)

### Security Rules
- **No resources exposed directly to the Internet** (all access through Appgate)
- **No production, customer, or sensitive data** in sandbox environments
- Cloud Security team **auto-remediates** insecure configs (e.g., open SSH inbound rules)
- Resources auto-deleted after **90 days** (notifications sent at 30 days, then daily at 3 days before deletion)
- For exceptions, file an [Auto-Remediation Exception Request](https://datadoghq.atlassian.net/jira/software/c/projects/CLOUDSEC/form/3428)

### Best Practices for Investigations
- **Tag with the SCRS ticket number** in the service tag (e.g., `service:scrs-1512-investigation`)
- **Tear down resources same day** when possible, don't leave things running overnight
- **Use the smallest resource that works** (e.g., `t3.micro` for basic agent testing)
- **Don't modify or delete resources you didn't create** unless confirmed with the owner
- **Never remove** cloud accounts/subscriptions from Demo Org `11287` or HQ Org `2`
- Check the [DataDog/sandbox repo](https://github.com/DataDog/sandbox) for pre-built Vagrant environments before building from scratch

### Confluence References
- [Team-Specific Cloud Sandboxes](https://datadoghq.atlassian.net/wiki/spaces/CLOUDA/pages/5129666770)
- [AWS, Azure, GCP Sandbox Environments for GSE](https://datadoghq.atlassian.net/wiki/spaces/TS/pages/328434517)
- [Sandbox Cloud Environment Security Policy](https://datadoghq.atlassian.net/wiki/spaces/SECENG/pages/4694639807)
- [Vagrant and Sandboxes](https://datadoghq.atlassian.net/wiki/spaces/TS/pages/4366600557)

## Style
- Never use em dashes in any output. Use commas, periods, parentheses, or rewrite the sentence instead.
