Generate a monthly escalation report for the SCRS JIRA project.

The argument is an optional month in YYYY-MM format: $ARGUMENTS

If no argument is given, default to the previous calendar month.

---

## Step 1 — Determine target month and date range

Parse `$ARGUMENTS` as YYYY-MM. If empty or missing, use the previous calendar month relative to today.

Calculate:
- `first_day`: YYYY-MM-01
- `last_day`: last calendar day of the month (e.g. 2026-03-31)
- `month_label`: human-readable label (e.g. "March 2026")

Confirm to yourself what month you are reporting on before proceeding.

---

## Step 2 — Check Atlassian MCP

If the Atlassian MCP is not authenticated, stop and tell the user to run `/mcp` and authenticate "claude.ai Atlassian" before continuing.

Use `datadoghq.atlassian.net` as the cloudId for all Atlassian MCP calls.

---

## Step 3 — Fetch resolved tickets (paginated)

Fetch all SCRS tickets resolved in the target month using this JQL:

```
project = SCRS
AND statusCategory = Done
AND resolutiondate >= "YYYY-MM-01"
AND resolutiondate <= "YYYY-MM-DD"
ORDER BY resolutiondate ASC
```

Substitute the actual first and last day values.

Call `mcp__atlassian__searchJiraIssuesUsingJql` with:
- `maxResults`: 100
- `fields`: `["summary", "status", "labels", "resolutiondate", "resolution", "created", "updated", "assignee", "issuetype", "priority", "description"]`
- `responseContentFormat`: `"markdown"`

Collect the `nodes` array from the response. If the response includes a `nextPageToken`, call again with that token and append the results. Repeat until `isLast` is true or no `nextPageToken` is returned.

Accumulate all tickets into a single flat array.

---

## Step 4 — Fetch engineering and PM escalation keys

Run two JQL queries in parallel to identify which resolved tickets passed through engineering or PM lanes. These queries use status history so they catch tickets that moved through a status even if they later moved to Done.

**Engineering escalations:**
```
project = SCRS
AND statusCategory = Done
AND resolutiondate >= "YYYY-MM-01"
AND resolutiondate <= "YYYY-MM-DD"
AND status was in ("Engineering Triage", "Engineering - In Progress")
ORDER BY resolutiondate ASC
```

**PM escalations (feature gaps passed to product):**
```
project = SCRS
AND statusCategory = Done
AND resolutiondate >= "YYYY-MM-01"
AND resolutiondate <= "YYYY-MM-DD"
AND status was in ("PM Triage", "PM - In Progress")
ORDER BY resolutiondate ASC
```

For each query, call `mcp__atlassian__searchJiraIssuesUsingJql` with:
- `maxResults`: 100
- `fields`: `["summary", "issuetype"]`
- `responseContentFormat`: `"markdown"`

Paginate if needed (same approach as Step 3). Collect only the `key` values from each result set.

Store as `eng_keys` (list of ticket keys) and `pm_keys` (list of ticket keys).

---

## Step 5 — Fetch open ticket count

Fetch the count of tickets created this month that are not yet resolved, using this JQL:

```
project = SCRS
AND statusCategory != Done
AND created >= "YYYY-MM-01"
AND created <= "YYYY-MM-DD"
```

Call `mcp__atlassian__searchJiraIssuesUsingJql` with `maxResults: 1`. Read the total from the response if available, otherwise count the nodes. If pagination is needed (isLast is false), note "100+" as the count rather than fetching all pages.

Store this as `open_count`.

---

## Step 6 — Save raw data to cache

Create the directory `reports/YYYY-MM/raw/` (using the actual year and month).

Write three files using the Bash tool (use python3 -c to write JSON safely):

**`reports/YYYY-MM/raw/tickets.json`**

A JSON array containing every ticket object collected in Step 3. Write all tickets as a flat array. Each element is the full ticket object as returned by the MCP (with `key` and `fields` at the top level).

**`reports/YYYY-MM/raw/escalations.json`**

```json
{
  "eng": ["SCRS-XXXX", ...],
  "pm": ["SCRS-XXXX", ...],
  "jql_eng": "<exact JQL used for eng query>",
  "jql_pm": "<exact JQL used for PM query>"
}
```

**`reports/YYYY-MM/raw/metadata.json`**

```json
{
  "month": "YYYY-MM",
  "first_day": "YYYY-MM-01",
  "last_day": "YYYY-MM-DD",
  "jql_resolved": "<the exact JQL used>",
  "fetched_at": "<ISO timestamp of now>",
  "total_fetched": <number of tickets>,
  "open_created_this_month": <open_count>
}
```

Confirm all three files have been written before proceeding.

---

## Step 7 — Run the analysis script

Run the following command using the Bash tool:

```bash
python3 scripts/monthly_report.py YYYY-MM
```

Substitute the actual year and month. The script will:
- Read the cached tickets and escalations
- Apply exclusion filters (deletion requests, feature requests)
- Render the full report to `reports/YYYY-MM/report.md`
- Print a summary

If the script exits with an error, report the error to the user and stop.

---

## Step 8 — Display summary

Read `reports/YYYY-MM/report.md` and display the **Volume Summary** (Section 1) and **Engineering Escalations** (Section 5) tables to the user inline.

Then tell the user:

> Full report written to `reports/YYYY-MM/report.md`.
>
> Next steps:
> - **Phase 3** (LLM classification for product area, recurring issues, self-served, doc gaps): run `/monthly-report YYYY-MM` again once Phase 3 is implemented
> - To re-fetch all data from JIRA and regenerate: run `/monthly-report YYYY-MM` again (cache will be overwritten)
