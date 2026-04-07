# MCP Tools - Five Live Servers

Five MCP servers are available. Use the **direct** server for JIRA, Confluence, GitHub, Slack, and Datadog when possible.

## Server: `atlassian` (Direct JIRA + Confluence)

**Use this for all JIRA and Confluence access.** Do NOT use Glean or jira_client.py for these.

```
- Fetch a JIRA ticket:      jira_get_issue          { issue_key: "SCRS-1951" }
- Search JIRA:              jira_search             { jql: "project = SCRS AND ...", fields: [...] }
- Get Confluence page:      confluence_get_page     { page_id: "1234567890" }
- Search Confluence:        confluence_search       { query: "appsec PHP tracer" }
```

## Server: `github` (Direct GitHub API)

**Use this for all GitHub access** -- searching repos, reading files, browsing PRs/issues.

```
- Search repos:             search_repositories     { query: "dd-trace-php org:DataDog" }
- Search code:              search_code             { query: "DD_APPSEC_ENABLED repo:DataDog/dd-trace-php" }
- Read a file:              get_file_contents       { owner: "DataDog", repo: "dd-trace-php", path: "appsec/README.md" }
- Search issues/PRs:        search_issues           { query: "appsec repo:DataDog/dd-trace-php" }
- List PRs:                 list_pull_requests      { owner: "DataDog", repo: "dd-trace-php" }
```

**Note:** The GitHub PAT is a fine-grained token with a 30-day expiry. If GitHub calls start failing with auth errors, run `ddtool auth github token` to get a fresh token and update `.mcp.json`.

## Server: `slack` (Direct Slack Access)

**Use this for searching Slack channels and messages directly.** Prefer this over Glean's `app: "slackentgrid"` filter for Slack-specific searches, since it gives direct access to channels and threads.

Requires OAuth on first use -- a browser window will open for Slack authentication.

## Server: `datadog` (Datadog Platform)

**Use this for direct access to Datadog monitors, dashboards, logs, metrics, and other platform data.** Useful during investigations to check customer-facing behaviors, verify monitor configurations, or explore platform features.

Requires OAuth on first use -- a browser window will open for Datadog authentication (Okta SSO).

## Server: `glean_default` (Glean - cross-source search)

Use Glean for **cross-source searches** where you don't know which system has the answer. Also useful for AI synthesis via `chat`.

```
- Search Slack:             search   { query: "SCRS-1951", app: "slackentgrid" }
- Search everything:        search   { query: "keyword1 keyword2" }
- AI synthesis:             chat     { message: "what's the pattern for X?" }
- Fetch any URL:            read_document  { urls: ["https://..."] }
```

### Parsing `read_document` responses

`read_document` uses **capitalised keys** -- `data['Documents']`, `d['Title']`, `d['Url']`, `d['Content']`.
`search` uses **lowercase keys** -- `data['documents']`, `d['title']`, `d['url']`, `d['snippets']`.

## Investigation Priority Order

1. **Atlassian MCP** -- fetch the JIRA ticket directly (`jira_get_issue`)
2. **Atlassian MCP** -- search JIRA for similar historical cases (`jira_search`)
3. **Atlassian MCP** -- check Confluence for relevant docs (`confluence_search`)
4. **Slack MCP** -- search Slack for team discussions (direct access)
5. **Datadog MCP** -- check platform data relevant to the investigation
6. **GitHub MCP** -- search code/issues/PRs directly (`search_code`, `search_issues`)
7. **Glean** -- cross-source search or AI synthesis when unsure where info lives
8. **`jira_client.py`** -- last resort only if MCP tools fail
