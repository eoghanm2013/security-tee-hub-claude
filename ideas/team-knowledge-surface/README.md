# Team Knowledge Surface

**Status:** Concept
**Effort:** Medium
**Impact:** High (multiplies across the team)

## Problem

The sandbox suite, playbooks, investigation patterns, and `.cursorrules` methodology are all valuable to every TEE on the team. But right now they're locked in a personal Cursor workspace. Adoption requires cloning the repo, using Cursor, setting up MCP servers, and understanding the workflow. That limits the audience to one person.

## Idea

Make the reusable knowledge accessible to all TEEs, regardless of their tooling preferences. Two approaches (not mutually exclusive):

### Path A: Extract and publish (low effort)

The standalone assets don't need Cursor to be useful:

- **[Sandbox suite](https://github.com/eoghanm2013/security-sandbox-suite)** -- Now its own public repo. Publish the README and playbooks to Confluence so any TEE can spin it up.
- **Investigation patterns** (once the knowledge flywheel is running) -- These are markdown files. Publish to Confluence or a shared repo.
- **Product area docs** -- Same. Confluence pages with links back to the playbooks.

This is mostly a publishing step. The `publish_confluence.py` script already exists for the sandbox suite. Extend it to cover docs/ and patterns.

### Path B: Shared TEE Hub instance (higher effort, more leverage)

The Flask web app already has search, archive browsing, docs navigation, and investigation views. If it ran on a shared server:

- Any TEE could search the pattern database and archive
- Investigations could be visible to the team (not just the assigned TEE)
- The knowledge base would be the team's, not one person's

This doesn't mean abandoning the Cursor workflow. The AI investigation still happens locally. But the outputs (patterns, archives, docs) flow into a shared surface.

## What exists already

- `app/server.py` -- Full Flask web app with search, archive, docs, investigation views
- Confluence publishing scripts (previously in sandbox suite)
- Playbooks for all 10 product areas
- The [sandbox suite](https://github.com/eoghanm2013/security-sandbox-suite) with reproduction environments

## Open questions

- Is Confluence the right surface, or would a lightweight hosted app be better?
- Who maintains the shared knowledge base? One person curating, or everyone contributing?
- How do you handle sensitive investigation details that shouldn't be team-visible?
- Would other TEE teams (not just security) benefit from this pattern?
