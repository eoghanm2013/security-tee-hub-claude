# Workspace Setup Detection

Before starting any investigation work, check whether this workspace has been configured:

1. Check if `.mcp.json` exists in the project root.
2. If it is **missing**, the workspace needs setup. Follow the setup flow below.
3. If it exists, skip setup -- the workspace is ready.

# Setup Flow

When `.mcp.json` does not exist, or the user asks to "set up", "get started", "configure", or "reconfigure" the workspace:

## How it works

Atlassian (JIRA + Confluence), Glean, Slack, and Datadog all use **OAuth/SSO** -- no tokens needed. They will prompt the user to log in via browser on first use.

GitHub is the only server that needs a token, and it's optional.

## Step 1: Ask about GitHub

Ask the user if they want GitHub code search (optional). If yes, they need a GitHub PAT:
- Generated at: https://github.com/settings/tokens?type=beta
- Needs Contents + Metadata read permissions
- Must authorize SSO for the DataDog org

If they don't need GitHub or don't have a token ready, skip it.

## Step 2: Run the setup script

Run the setup script:

```
python3 scripts/setup.py --skip-github
```

Or with a GitHub token:

```
python3 scripts/setup.py --github-token "GITHUB_TOKEN"
```

If the user already has a `.mcp.json` and wants to reconfigure, add `--reconfigure`.

## Step 3: Post-setup instructions

After the script succeeds, tell the user:

1. **Connect MCP servers** -- Type `/mcp` in the Claude Code panel to see all servers. Click "Authenticate" for each OAuth server (Atlassian, Glean, Slack, Datadog) to complete the browser-based SSO flow. This is a one-time step.
2. **Verify** -- Try: "Use MCP to fetch JIRA ticket SCRS-1885" to confirm MCP servers loaded.

# Reconfiguring

If the user needs to add GitHub later or reconfigure, run:

```
python3 scripts/setup.py --reconfigure --github-token "..."
```

Then run `/mcp` to reconnect servers.
