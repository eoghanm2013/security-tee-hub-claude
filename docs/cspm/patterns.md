# CSPM (Cloud Security Misconfigurations) - Patterns

Known investigation patterns for CSPM. Each entry captures a reusable insight from a past investigation.

---

### SNS topic misconfiguration signal is correct despite customer claim of no change (2026-03)

- **Symptoms:** Customer reported a misconfiguration signal for an SNS topic they claimed hadn't changed in 9 months. Other SNS topics in different accounts with seemingly similar policies were not flagged.
- **Product:** CSPM
- **Root cause:** CloudTrail logs confirmed the flagged SNS topic was actually created on the same day the signal fired, with a policy that included unrestricted `Principal: "*"` statements without conditions. The unflagged topics in other accounts had `Condition` blocks (e.g., `AWS:SourceOwner`) restricting access, which the CSPM rule correctly treats as not publicly accessible.
- **Resolution:** Customer's flagged topic was correctly identified. They remediated by removing the unrestricted statements. The unflagged topic in the other account was correctly passing due to its conditional restriction.
- **Risk:** Customers often assume similar-looking policies are equivalent. Always check CloudTrail for actual creation/modification times and compare full policy JSON including Condition blocks.
- **Source:** SCRS-2017

### Azure resource recreated with same name treated as same entity by Findings Platform (2026-02)

- **Symptoms:** Customer deleted an Azure storage account and recreated it with the same name. The new resource triggered the same misconfiguration rule, but no new email notification was sent. The UI showed it as a continuation of the old finding.
- **Product:** CSPM
- **Root cause:** Working as designed. Azure builds resource IDs using the resource path, which is the same when a resource is recreated with the same name. The Findings Platform uses resource ID as the entity identifier, so the new finding is treated as a new version of the previous one, not a new detection.
- **Resolution:** Explained expected behavior to customer. No workaround currently exists for this behavior.
- **Risk:** Customers expecting per-instance notification uniqueness will be surprised.
- **Source:** SCRS-1946

### Chrony and Timesyncd compliance rules fail when NTP servers are not explicitly configured (2026-03)

- **Symptoms:** CSPM compliance rules for Systemd Timesyncd and Chrony server configuration failing on customer hosts despite customer believing configuration was correct.
- **Product:** CSPM
- **Root cause:** Customer had not actually run the remediation scripts or manually added NTP server entries. The default chrony.conf and timesyncd.conf did not include explicit NTP server/pool directives as required by the compliance checks.
- **Resolution:** Add NTP server entries to `/etc/chrony/chrony.conf` (e.g., `server 0.ubuntu.pool.ntp.org`) and create `/etc/systemd/timesyncd.conf.d/99-compliance.conf` with `[Time] NTP=...`. Verify with `security-agent compliance check --report`.
- **Risk:** Customers often assume their NTP config is correct because time syncs fine, but the compliance rules check for explicit server/pool directives. Continuation of SCRS-1929 pattern: always verify customers have actually applied remediation before investigating further.
- **Source:** SCRS-1995
