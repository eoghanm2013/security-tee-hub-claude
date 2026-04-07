# Cloud SIEM - Patterns

Known investigation patterns for Cloud SIEM. Each entry captures a reusable insight from a past investigation.

---

### Risk Insight notification rules 403 error on Legacy SIEM SKU (2026-03)

- **Symptoms:** Customer received "Unable to load data" error when trying to create a Risk Insight notification rule. Browser console showed 403 on `/api/ui/security-entities/notification-rules/count`.
- **Product:** Cloud SIEM
- **Root cause:** Customer was on the Legacy SIEM SKU, which does not include the Risk Insight notification feature. The UI still showed the option but the API rejected the request with 403.
- **Resolution:** Inform customer this feature requires the current SIEM SKU. Engineering confirmed the UI will be updated to hide this option for Legacy SKU customers.
- **Risk:** UI shows features that are not available on the customer's plan, creating confusion. Check SKU before deep-diving on 403s for security features.
- **Source:** SCRS-2015

### Security Signals auto-refresh clears Create Case modal content (2026-02)

- **Symptoms:** When creating a case from a Security Signal, the auto-refresh of the Signals list caused the Create Case modal contents to be lost. Customer was using Zen (Firefox-based) browser.
- **Product:** Cloud SIEM
- **Root cause:** The Signals page periodic auto-refresh was re-rendering the page, which reset the contents of the open Create Case modal. Bug in the UI component lifecycle.
- **Resolution:** Engineering deployed a fix. Workaround was to use the Create Case button from the side panel instead of the scrolled-down Signals window.
- **Risk:** None post-fix. UI bug.
- **Source:** SCRS-1965

### Content Packs showing "Broken" due to high-cardinality source tags (2026-03)

- **Symptoms:** All Cloud SIEM Content Packs displayed as "Broken" (no logs received in 72 hours), despite logs flowing correctly and detection rules generating signals.
- **Product:** Cloud SIEM
- **Root cause:** Customer's logs had S3 file paths as source tags (e.g., `s3://bucket/path/to/file.json.log.gz`), creating ~35,000 unique source tag values per week. The content pack health status API queries Estimated Usage Metrics (EUM), which hit a `ResourceExhausted` error due to the extreme tag cardinality. The status query failure caused all content packs to fall back to "Broken".
- **Resolution:** (1) Stop ingesting logs with raw S3 paths as source tags, (2) Exclude `source:s3*` logs from the SIEM index filter. Logs and detections were unaffected; this was purely a UI/status display issue.
- **Risk:** High-cardinality source tags can silently break Content Pack status for the entire org. Actual detection and signal generation remains functional.
- **Source:** SCRS-2012

### Terraform provider v3.89.0 regression destroys OOTB queries on default rules (2026-03)

- **Symptoms:** After upgrading Terraform provider to v3.89.0, `terraform plan` showed diffs attempting to destroy existing queries on `datadog_security_monitoring_default_rule` resources that had been imported without specifying the optional `query` argument.
- **Product:** Cloud SIEM
- **Root cause:** PR #3521 in the Terraform provider changed the Read function to unconditionally populate `case` and `query` blocks from the API response into state. This fixed the import use case but regressed existing managed resources where `query` was intentionally omitted.
- **Resolution:** Engineering fix in progress. Workaround: pin to provider version before v3.89.0, or explicitly add the `query` blocks to the Terraform config to match the API state.
- **Risk:** Running `terraform apply` with this version will destroy OOTB detection rule queries. Pin the provider version until the fix is released.
- **Source:** SCRS-1976
