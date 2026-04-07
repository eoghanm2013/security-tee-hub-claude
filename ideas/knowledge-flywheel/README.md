# Knowledge Flywheel

**Status:** Concept
**Effort:** Medium
**Impact:** High (compounds over time)

## Problem

Every investigation produces insights (root cause patterns, common misconfigurations, product-specific gotchas), but those insights die in the investigation folder. When the ticket is archived, the knowledge effectively disappears. The AI can search old JIRA tickets, but it can't learn from how *we* investigated them.

The `docs/` directory is designed for this purpose but is currently empty. The "pattern recognition workflow" in `.cursorrules` references consulting `docs/` for known patterns, but there's nothing there.

## Idea

Make knowledge extraction automatic. When an investigation is closed:

1. **Extract the pattern** -- symptom fingerprint, product area, root cause category, resolution type
2. **Write it to `docs/{product_area}/patterns.md`** -- append a structured entry
3. **Index it for future search** -- the AI and web app can find it instantly next time

Over time, this builds a living knowledge base that makes every future investigation faster. The first time you hit a new pattern takes 2 hours. The second time takes 10 minutes because the pattern is already documented.

## What it could look like

When you say "close out this investigation," the system:

- Reads `notes.md` and `response.md`
- Extracts: symptom summary, root cause, resolution, product area, affected versions
- Formats a pattern entry and appends it to the right `docs/` file
- Optionally asks you to review before writing

## Pattern entry format (example)

```markdown
### PHP-FPM Worker Exhaustion with AppSec (2026-02)

**Symptoms:** High CPU, PHP-FPM workers maxed out, application timeouts after enabling AppSec
**Product:** AAP
**Root cause:** DD_APPSEC_ENABLED causes the tracer to inspect every request, doubling worker load
**Resolution:** Increase pm.max_children proportionally, or use pm=dynamic with higher max_spare
**Risk note:** Reducing workers (the intuitive fix) makes it worse
**Source:** SCRS-1885
```

## Open questions

- Should patterns be one file per product area, or one file per pattern?
- How much should the AI auto-generate vs. how much should the TEE curate?
- Should this integrate with the web app's search, or is markdown + AI search enough?
