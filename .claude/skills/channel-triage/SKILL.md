Scan #support-code-security, #support-cloud-security, and #support-security-threats for threads in the last 48 hours with no real human response. Triage each thread for channel routing and information quality, then investigate on request.

No arguments required.

---

## Step 1 — Check Slack MCP

If the Slack MCP is not authenticated, stop and tell the user to run `/mcp` and authenticate "claude.ai Slack" before continuing.

---

## Step 2 — Resolve channel IDs, then fetch recent messages

`slack_read_channel` requires channel IDs, not names. Use `slack_search_channels` to look up all three in parallel before fetching messages. The expected channels are:

| Name | Expected ID (cache — verify on first use) |
|---|---|
| `#support-code-security` | `C08172NACQN` |
| `#support-cloud-security` | `CUGB0M85T` |
| `#support-security-threats` | `C02H3AX9M5F` |

If a lookup returns a different ID than the cached value, use the live result and note the discrepancy.

Once IDs are confirmed, use `slack_read_channel` on all three in parallel. Filter to messages posted within the last 48 hours by comparing the message timestamp (`ts`, a Unix epoch float) against `now - 172800` seconds.

For each message, note: channel, `ts`, `user`, `text`, `reply_count`, `thread_ts`.

---

## Step 3 — Identify unanswered threads

A message is a candidate if it was posted in the last 48 hours. For any candidate with `reply_count > 0`, read the full thread using `slack_read_thread`. Check each reply using bot/automation heuristics.

**A thread is unanswered if:**
- `reply_count` is 0 or missing, OR
- Every reply triggers at least one bot indicator below

**Bot/automation heuristics (no profile API calls):**
- `subtype` is `bot_message`, `slackbot_response`, or `tombstone`
- `bot_id` field is present on the message object
- `username` or display name contains (case-insensitive): `bot`, `app`, `webhook`, `zendesk`, `github`, `zapier`, `datadog`, `pagerduty`, `automat`, `workflow`, `notify`, `alert`
- Message text matches Zendesk notification patterns: starts with "New ticket", "Ticket #", "ZD#", "[Zendesk]", or "A new ticket has been"
- Username is `EEKS` or user ID is `U06NMGUCQ74` (internal knowledge bot — always treat as automation regardless of display name)

**Also exclude replies from the thread's original poster.** If the only non-bot replies are from the same user who posted the original message, the thread is still unanswered — they are adding context, not responding to themselves.

A single reply from a *different* user without any of the above indicators means the thread is answered — skip it. Do not apply judgment about whether the reply actually resolved the question. Routing pings, tag-ons, "looking into this" replies — all count as human engagement. The goal is untriaged threads only.

Build a flat list of unanswered threads across all three channels with: channel name, poster, timestamp (human-readable UTC), message text, reply count.

---

## Step 4 — Check channel routing

For each unanswered thread, read the message content and identify what product or area it's about. Then check if it belongs in that channel.

**Routing rules:**

| Channel | Products and keywords |
|---|---|
| `#support-cloud-security` | CSPM, misconfig, compliance, CIS, STIG, benchmark, posture, VM, CVE, vulnerability, agentless, scanning, CIEM, IAM, identity, privilege escalation, cloud posture, cloud account |
| `#support-code-security` | SAST, SCA, `DD_APPSEC_SCA_ENABLED`, software composition, dependency, library CVE, IAST, `DD_IAST_ENABLED`, tainted, static analysis, code scanning, secret detection |
| `#support-security-threats` | SIEM, detection rule, signal, log detection, Workload Protection, CWS, eBPF, runtime security, FIM, DNS, AAP, AppSec, `DD_APPSEC_ENABLED`, WAF, in-app WAF, HTTP threat, account takeover, tracer security |

**Verdict for each thread:**
- **Correct** — product matches the channel it was posted in
- **Misrouted → #correct-channel** — product clearly belongs in a different channel; state which one
- **Unclear** — can't determine the product area from the message content alone

---

## Step 5 — Assess information quality

For each unanswered thread, assess whether there's enough context to start investigating. Use judgment — a simple "how do I enable X" needs less context than a "why is X not working" bug report.

**Rate each thread:**
- **Actionable** — enough to investigate now (product identified, symptom or question clear, basic environment info present where relevant)
- **Needs more info** — coherent problem statement but missing something specific; note exactly what is missing (e.g. "missing tracer version", "no error message or signal URL provided", "no steps to reproduce")
- **Too vague** — can't determine what the actual problem is

---

## Step 6 — Build and save the triage log

Write a triage log to `slack-triage/YYYY-MM-DD.md` (use today's date). If the file already exists, overwrite it with the latest run.

Format:

```markdown
# Slack Triage — YYYY-MM-DD

Generated: HH:MM UTC

## #support-cloud-security

### [Actionable] One-line summary of the question

- **Poster:** @username
- **Time:** HH:MM UTC
- **Routing:** Correct | Misrouted → #channel | Unclear
- **Info quality:** Actionable | Needs more info: X | Too vague
- **Message:** (first ~300 chars of message text)
- **Investigation:** _(filled in during Step 8)_

---

### [Needs more info: missing tracer version] One-line summary

...

## #support-code-security

...

## #support-security-threats

...
```

Within each channel section, order threads: **Actionable** first, then **Needs more info**, then **Too vague**.

---

## Step 7 — Present triage to user

If there are no unanswered threads, tell the user:
> "All threads in the last 48 hours have received a human response — nothing to triage right now."
Then stop. Do not proceed to Step 8.

Otherwise, display the triage summary in the conversation, grouped by channel with the same ordering (Actionable first). For each thread show:
- Priority badge: **[Actionable]**, **[Needs more info: X]**, or **[Too vague]**
- Routing verdict
- One-line question summary, poster, and timestamp

After displaying, tell the user where the log was saved, then ask:
> "Which of these do you want me to investigate? You can say 'all actionable', name specific ones, or 'all'."

---

## Step 8 — Investigate

Before starting, verify the Atlassian MCP is authenticated. If not, stop and tell the user to run `/mcp` and authenticate "claude.ai Atlassian" before continuing — it's needed for JIRA and Confluence searches in the steps below.

For each thread the user selects, run a full investigation in this order. Work through all selected threads before presenting final findings.

### 8a — Check Slack for prior mentions

Search Slack for prior discussions about the same issue. Use `slack_search_public_and_private` with 2-3 keyword combinations extracted from the question (product name + symptom keywords). Look across:
- The same support channel (for recurring questions)
- Engineering or internal team channels (for known issues or workarounds)
- Any previous resolutions or threads linking to tickets

Note any relevant prior threads with their links and key findings.

### 8b — Check the pattern database

Read `docs/{product_area}/patterns.md` for known patterns matching the symptoms.

If a pattern matches, state: "Matches [pattern name] from SCRS-XXXX" and include the resolution.

Determine the product area from this mapping:
- `aap` — App and API Protection (AppSec, ASM, WAF, in-app WAF, `DD_APPSEC_ENABLED`)
- `siem` — Cloud SIEM (detection rules, signals, log detection)
- `workload_protection` — Workload Protection / CWS (eBPF, runtime security, FIM, DNS)
- `cspm` — Cloud Security Misconfigurations (compliance, benchmarks, CIS, STIG)
- `vm` — Vulnerability Management (CVEs, agentless, CVSS)
- `ciem` — Identity Risk Management (IAM, privilege escalation)
- `sast` — Static Application Security Testing
- `sca` — Software Composition Analysis
- `iast` — Interactive Application Security Testing
- `common` — Cross-product or agent-level issues

### 8c — Search JIRA for similar cases

Search the SCRS project for similar historical tickets using symptom keywords. Pull 3-5 most relevant matches and check for resolutions, workarounds, or engineering notes.

### 8d — Check Confluence

Search Confluence for relevant documentation, known issues, or runbooks matching the question.

### 8e — Search GitHub if needed

If the question appears to be a code-level bug, version-specific regression, or tracer behaviour, search the relevant DataDog repo (e.g. `dd-trace-php`, `dd-trace-java`, `datadog-agent`, `datadog-agent-macos-build`) for related issues, PRs, or source context.

### 8f — Synthesise and record findings

Write a concise finding for each investigated thread (3-5 sentences):
- **Root cause or working theory**
- **Recommended next step** for the TSE who posted (what to ask for, what to try, or what to reply)
- **Sources** — JIRA ticket, GitHub issue, Confluence page, prior Slack thread (with links)

Append this finding to `slack-triage/YYYY-MM-DD.md` under the relevant thread's **Investigation** field.

### 8g — Present findings to user

After all selected threads are investigated, display findings grouped by channel (same ordering as triage). For each thread:
- Thread summary and poster
- Root cause or working theory
- Recommended next step
- Relevant links (internal only — flag anything that should not be shared externally verbatim)
