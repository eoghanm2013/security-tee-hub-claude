# Session Naming

At the start of every conversation, set the session title using the first available identifier in this order:

1. **SCRS ticket ID** -- if the user mentions or pastes a JIRA ticket (e.g. `SCRS-1951`), use that as the title: `SCRS-1951`
2. **Zendesk ticket ID** -- if the user references a Zendesk ticket number (e.g. `#123456` or `ZD-123456`), use that: `ZD-123456`
3. **Slack channel + issue title** -- if the context comes from a Slack thread or channel, use: `#channel-name - brief issue description`
4. **Fallback** -- if none of the above are present, use a short descriptive title based on the product area and symptom, e.g. `AAP - trace sampling anomaly` or `SIEM - rule not triggering`

Use the `/title` command (or equivalent session rename mechanism) to set this as early as possible in the conversation, once the identifier is known. If the identifier only becomes clear mid-conversation, set the title then.
