# AAP (App and API Protection) - Patterns

Known investigation patterns for AAP (formerly ASM/AppSec). Each entry captures a reusable insight from a past investigation.

---

### AppSec not activating via Remote Config due to explicit JVM flag (2026-02)

- **Symptoms:** Fleet Automation showed AppSec as "Applied/Success", APM traces flowing, but `ps -ef | grep java` showed `-Ddd.appsec.enabled=false`. Services didn't appear in AppSec configuration list. UI showed "manual installation required" instead of remote activation.
- **Product:** AAP
- **Root cause:** The `-Ddd.appsec.enabled=false` JVM argument was explicitly set in the startup config. When this flag is present, the Java tracer disables Remote Configuration activation for AppSec entirely. The local flag takes priority over Fleet Automation/RC. Fleet Automation "Success" only means the Agent config was updated, not the tracer.
- **Resolution:** Remove `-Ddd.appsec.enabled=false` entirely from JVM startup arguments (don't set it to `true`, just remove it). Restart services. Activate via Security > App & API Protection > Services. Batch jobs without HTTP servers are not compatible with AppSec.
- **Risk:** Common confusion point. Fleet Automation success status is misleading when local tracer flags override RC. AppSec requires an HTTP server to function.
- **Source:** SCRS-1958

### RASP false positive on parameterized SQL queries with Spring Data (2026-03)

- **Symptoms:** SQL injection attack attempt showed a 200 response and was marked as "Harmful" in AAP. Customer concerned about security posture.
- **Product:** AAP
- **Root cause:** Backend RASP false positive. The application used Spring Data with parameterized queries, so the SQL injection payload was treated as a literal string (confirmed by `ProgramGroupNotFoundException` in the trace). RASP incorrectly classified the parameterized query execution as a successful attack.
- **Resolution:** Backend fix deployed via PR (dd-go). The attack was never successful; the application was safe. Customer can disregard the "Harmful" classification for this trace.
- **Risk:** RASP false positives on parameterized queries can cause unnecessary alarm. Check the trace for evidence of parameterization (ORM usage, exceptions treating payload as literal) before concluding an attack was successful.
- **Source:** SCRS-2005

### Java tracer upgrade causes CPU saturation from WAF processing malicious payloads (2026-03)

- **Symptoms:** After upgrading Java tracer from 1.49 to 1.58, service hit 100% CPU and entered pod restart loop. Large volume of AppSec security signals (Jackson-databind deserialization attacks). Disabling AAP stabilized the service.
- **Product:** AAP
- **Root cause:** Multiple changes between tracer versions compounded: extended request body collection (#8748, #9428), improved Jackson node introspection (#8980), and libddwaf upgrade to 17.1.0 (#9486). Together, these caused the WAF engine to deeply parse complex attacker-supplied JSON objects without adequate depth limits, spiking CPU under active attack traffic.
- **Resolution:** Engineering bug filed (APPSEC-61693), fix in progress. Immediate workaround is to disable AAP or pin to tracer 1.49. Long-term fix requires max_depth control for nested object parsing.
- **Risk:** Major tracer version jumps (9+ minor versions) with AAP enabled can introduce unexpected CPU cost under attack traffic. Test in staging first. Confirmed product bug, not configuration.
- **Source:** SCRS-2006

### Node.js AAP shows "Not Supported" for services using @smithy framework (2026-02)

- **Symptoms:** AAP showing "Not Supported" for certain Node.js services (BFF services). `integrations_loaded` in tracer config showed `http, http2, aws-sdk, net, dns` with no `fastify` loaded, despite customer believing they were on Fastify.
- **Product:** AAP
- **Root cause:** Services were actually using `@smithy` (AWS SDK HTTP layer), not Fastify. K9 engineering confirmed no Fastify references in service catalog. Additionally, dd-trace version 5.56.0 was one version too old for Fastify AAP support (added in 5.57.0).
- **Resolution:** Confirmed unsupported framework. Suggested K8s standalone AAP as a workaround. For Fastify users, upgrade to dd-trace >= 5.57.0.
- **Risk:** Always check `integrations_loaded` in tracer config to verify the actual framework, not what the customer assumes. The presence of a framework in `package.json` doesn't mean the tracer detects it.
- **Source:** SCRS-1931

### PHP AppSec sidecar fails on SELinux-enforcing hosts due to memfd execution block (2026-02)

- **Symptoms:** Recurring PHP-FPM errors after enabling AppSec: `[ddtrace] Failed signaling lifecycle end: Broken pipe`, `[ddappsec] Connection to helper failed`, `The sidecar transport is closed. Reconnecting...`. Apache + PHP-FPM on AlmaLinux 8.10.
- **Product:** AAP
- **Root cause:** SELinux blocking the sidecar trampoline execution. The sidecar writes its initial executable to a memfd and executes via `fexecve`/`execveat`. SELinux policies on AlmaLinux 8.10 block this execution path for the apache user.
- **Resolution:** Enable `DD_SPAWN_WORKER_USE_EXEC=true` (writes trampoline to temp directory and executes via path-based `execve` instead) and configure SELinux to allow apache user execution of files in the temporary directory.
- **Risk:** Affects any SELinux-enforcing RHEL-family system (RHEL, AlmaLinux, Rocky) running PHP AppSec. The default memfd execution path is silently blocked. Helper/sidecar debug log variables require exact syntax: `_DD_DEBUG_SIDECAR_LOG_METHOD` must start with underscore.
- **Source:** SCRS-1885

### Stale AAP services persist in UI when enabled via Remote Configuration (2026-03)

- **Symptoms:** Customer wanted to remove old disabled environments/services from the App & API Protection UI. Support-Admin couldn't disable them.
- **Product:** AAP
- **Root cause:** Services enabled via Remote Configuration (RC) persist in the UI even when no longer sending data. Support-Admin lacks permissions to disable these services.
- **Resolution:** Customer can deactivate services themselves from the UI. RC-enabled services persist until manually deactivated; env-var-enabled services auto-remove after 3 days without data.
- **Risk:** The distinction between RC-enabled and env-var-enabled service persistence is not well documented and causes confusion.
- **Source:** SCRS-1993
