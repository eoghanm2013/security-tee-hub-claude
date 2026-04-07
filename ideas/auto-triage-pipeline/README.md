# Auto-Triage Pipeline

**Status:** Concept
**Effort:** Medium-High
**Impact:** High (time savings on every investigation)

## Problem

The current investigation flow is TEE-initiated. A ticket lands, the TEE reads it, asks the AI to help, and manually guides the research. The TEE starts every investigation from a blank page, even when the answer might already exist somewhere.

## Idea

Flip the model. When a new ticket is assigned, the system does the research upfront and presents findings for the TEE to review.

**Current flow:**
1. Ticket arrives
2. TEE reads ticket
3. TEE asks AI to help
4. TEE guides research
5. TEE writes response

**Proposed flow:**
1. Ticket arrives
2. System auto-runs the investigation playbook (search similar cases, classify product area, pull relevant docs, check GitHub)
3. System writes a draft `notes.md` with findings and a confidence assessment
4. TEE reviews, corrects, deepens where needed
5. TEE approves or rewrites response

## How it could work

The `watcher.py` module already polls JIRA for new assignments. Extend it to:

1. **On new ticket assignment:** Trigger an intake analysis
2. **Search JIRA** for similar historical cases (match by symptoms, product area, error messages)
3. **Search Confluence** for relevant product documentation
4. **Check GitHub** for related issues or PRs (especially recently merged fixes)
5. **Classify** the ticket by product area and issue type
6. **Write draft `notes.md`** with what was found, flagging gaps in the escalation
7. **Assess confidence** -- "high confidence match to SCRS-1885 pattern" vs. "no similar cases found, novel issue"

For tickets that match a known pattern with high confidence (~30% of cases), the draft response might need nothing more than a quick review. For novel issues, the TEE still does the deep work, but with a head start instead of starting cold.

## Building blocks already in place

- `watcher.py` -- polls JIRA, detects new assignments
- `.cursorrules` -- encodes the investigation methodology
- MCP servers -- access to JIRA, Confluence, GitHub, Glean
- `analyzer.py` -- already does pre-analysis on flares and attachments
- Product area detection -- already classifies tickets by product

## Open questions

- Should this run inside Cursor (triggered by a command) or as a standalone service?
- How do you handle tickets where the auto-triage is wrong? (Confidence calibration)
- Should it generate a draft `response.md` too, or just research notes?
- Rate limiting on MCP/API calls if multiple tickets land at once
