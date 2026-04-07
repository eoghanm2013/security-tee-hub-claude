# Common / Cross-Product - Patterns

Known investigation patterns that span multiple product areas or relate to the Datadog Agent generally. Each entry captures a reusable insight from a past investigation.

---

### Security Agent exits immediately when no security products are enabled (2026-03)

- **Symptoms:** Customer reported Datadog Security Agent service stops on Windows hosts. Logs showed: "Datadog runtime security agent disabled by config" and "All security-agent components are deactivated, exiting."
- **Product:** Common (Security Agent)
- **Root cause:** No security products (CWS, CSPM, or Cloud SIEM) were enabled in `datadog.yaml`. The Security Agent requires at least one security product to remain running. Without any, it exits by design.
- **Resolution:** Explained that the Security Agent's function is specific to Datadog security products, not general host security. To keep it running, enable at least one product (CWS, CSPM) per the docs.
- **Risk:** Common misconception. The name "Security Agent" leads customers to think it provides security for the agent itself, rather than being the agent component for Datadog's security product suite.
- **Source:** SCRS-2004
