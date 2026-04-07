---
paths:
  - "investigations/*/notes.md"
  - "investigations/*/response.md"
---

# Close-Out Investigation: Pattern Extraction

When the user asks to "close out" an investigation, "extract patterns", or "wrap up" an investigation, follow this workflow.

## Step 1: Identify the investigation

Determine which investigation to close out. Check:
- The file currently open (if it's inside an `investigations/` folder)
- Or the ticket key the user mentions

Read both `notes.md` and `response.md` from the investigation folder.

## Step 2: Detect the product area

Determine the product area from the investigation content. The valid areas are:
- `aap` - App and API Protection (AppSec, ASM, WAF, In-App WAF)
- `siem` - Cloud SIEM (detection rules, security signals, log detection)
- `workload_protection` - Workload Protection (CWS, eBPF, runtime security, SBOM, FIM)
- `cspm` - Cloud Security Misconfigurations (compliance, benchmarks, CIS, STIG)
- `vm` - Vulnerability Management (CVEs, agentless scanning, CVSS)
- `ciem` - Identity Risk Management (IAM, privilege escalation, entitlements)
- `sast` - Static Application Security Testing
- `sca` - Software Composition Analysis (dependencies, library vulnerabilities)
- `iast` - Interactive Application Security Testing (tainted data, sources/sinks)
- `common` - Cross-product or agent-level issues

## Step 3: Generate the pattern entry

Extract a structured pattern from the investigation. Read `notes.md` and `response.md` carefully, then generate an entry in this exact format:

```markdown
### Short description (YYYY-MM)

- **Symptoms:** What the customer reported or what was observed
- **Product:** Product area name
- **Root cause:** What was actually wrong
- **Resolution:** How it was fixed or worked around
- **Risk:** Any caveats, things that could go wrong, or gotchas for next time
- **Source:** SCRS-XXXX
```

Guidelines:
- The short description should be specific and searchable (e.g. "PHP-FPM worker exhaustion with AppSec" not "AppSec issue")
- Symptoms should describe what someone would see before knowing the root cause
- Root cause should be the actual technical explanation
- Resolution should be actionable (what to do, not just what was wrong)
- Risk should capture what the TEE learned that isn't obvious
- If there's no clear pattern worth capturing (e.g. the investigation was a dead end or a simple config fix), say so and skip

## Step 4: Present for review

Show the generated pattern entry to the user. Ask them to confirm or edit before writing.

## Step 5: Write the pattern

Append the approved pattern entry to `docs/{product_area}/patterns.md`. Add it after the last existing entry (or after the comment block if the file has no entries yet).

## Step 6: Confirm

Tell the user:
- Pattern written to `docs/{area}/patterns.md`
- The investigation folder is preserved locally
- If they want to archive the JIRA data, they can use the Sync button in the TEE Hub web app
