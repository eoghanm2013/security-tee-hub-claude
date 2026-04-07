# Engineering Feedback Loop

**Status:** Concept
**Effort:** Medium
**Impact:** Medium-High (visibility + process improvement)

## Problem

The investigation workflow currently ends at "this is a bug, escalate to engineering." There's no structured feedback loop. Questions that go unanswered:

- Did engineering accept it as a bug?
- When did the fix ship?
- Did the fix actually resolve the customer's issue?
- Did the pattern recur after the fix?
- How long did the full cycle take (escalation to resolution)?

Without this data, you can't measure the impact of the TEE role, identify bottlenecks, or make a case for process improvements.

## Idea

Track the full lifecycle of escalations that result in engineering work. Build a lightweight dataset that connects JIRA tickets to GitHub issues/PRs and back to resolution.

### What to track

For each investigation that results in an engineering escalation:

| Field | Source | Example |
|-------|--------|---------|
| SCRS ticket | JIRA | SCRS-1885 |
| Product area | Auto-detected | AAP |
| Escalation date | JIRA status change | 2026-01-15 |
| Engineering ticket | Linked JIRA/GitHub issue | APPSEC-4521 |
| Fix PR | GitHub | DataDog/dd-trace-php#2847 |
| Fix release | GitHub release/tag | v1.4.2 |
| Resolution date | PR merge or release date | 2026-02-03 |
| Days to fix | Computed | 19 days |
| Customer confirmed fix | JIRA comment or status | Yes/No/Unknown |
| Pattern documented | docs/ entry exists | Yes/No |

### What this enables

- **Metrics:** Average time from escalation to fix, by product area
- **Bottleneck identification:** Which product areas are slowest to fix? Where do tickets stall?
- **TEE impact reporting:** "TEE investigations led to X bug fixes affecting Y customers this quarter"
- **Pattern closure:** When a fix ships, update the pattern database with the resolution and affected versions
- **Recurrence detection:** If the same pattern shows up after a fix supposedly shipped, flag it immediately

### Implementation approach

This doesn't need to be complex. A simple tracking file (`investigations/tracking.md` or a JSON/CSV) that gets updated as investigations progress. The watcher could auto-detect when linked engineering tickets close and prompt for an update.

Longer term, a dashboard view in the web app that shows the pipeline: open investigations, waiting on engineering, fixed, confirmed.

## What exists already

- JIRA ticket linking (SCRS tickets often link to engineering tickets)
- The archive captures resolution status
- The web app has a dashboard that could show pipeline metrics
- GitHub MCP can search for PRs and releases

## Open questions

- How much of this can be automated vs. manually maintained?
- Is a flat file enough, or does this need a proper data store?
- Should this be visible to engineering teams (transparency) or TEE-internal (operational)?
- Could this data feed into team OKRs or quarterly reviews?
