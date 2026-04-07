# IAST (Interactive Application Security Testing) - Patterns

Known investigation patterns for IAST. Each entry captures a reusable insight from a past investigation.

---

### System-wide DD_IAST_ENABLED breaks non-target .NET processes (2026-03)

- **Symptoms:** Enabling IAST by setting `DD_IAST_ENABLED=true` as a machine-level environment variable on Windows caused: (1) VisualCron service failing to start, (2) web application SSO login breaking. Both issues resolved when IAST was disabled.
- **Product:** IAST
- **Root cause:** Customer set `DD_IAST_ENABLED=true` at the system level, which caused the .NET profiler to attach to every .NET process on the host, including third-party services like VisualCron.
- **Resolution:** (1) Add `DD_PROFILER_EXCLUDE_PROCESSES=VisualCronService.exe` to exclude specific processes. (2) Remove system-level `DD_IAST_ENABLED` and set it per-application only on targeted services.
- **Risk:** System-wide .NET instrumentation can break any .NET process on the host. Always set per-application. This applies to all DD_* tracing/security env vars on .NET.
- **Source:** SCRS-2010
