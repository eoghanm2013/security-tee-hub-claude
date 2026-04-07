# Workload Protection - Patterns

Known investigation patterns for Workload Protection (formerly CWS). Each entry captures a reusable insight from a past investigation.

---

### CWS custom policy deployment on ECS Fargate shows "0 agents" (2026-02)

- **Symptoms:** Customer created a custom CWS policy but could not deploy it to any Fargate agent. UI showed "0 agents" when selecting tags.
- **Product:** Workload Protection
- **Root cause:** Fargate agents don't appear in the standard agent picker UI for custom policy deployment. The UI showing "0 agents" is expected behavior for Fargate.
- **Resolution:** Set `DD_EXTRA_TAGS` on the Datadog agent sidecar container, enter that tag when deploying the policy (ignore "0 agents" display), and verify deployment via Investigate page with `agent.rule_id:ruleset_loaded`.
- **Risk:** UI is misleading for Fargate deployments. Customer may assume policy didn't deploy when it actually did.
- **Source:** SCRS-1959

### Windows system-probe crash with FIM enabled on agent v7.72+ (2026-02)

- **Symptoms:** System-probe continuously restarting on Windows when upgrading to agent v7.72.2 with `fim_enabled: true`. Resolved by downgrading to v7.71.2 or disabling FIM. Hosts also running Sophos AV/FIM.
- **Product:** Workload Protection
- **Root cause:** Bug in the agent's Windows FIM/CWS implementation. Initial investigation pointed to Sophos interference, then to the Installer daemon's remote config loop, but ultimately a race condition in system-probe was identified. Fix PR: https://github.com/DataDog/datadog-agent/pull/47999
- **Resolution:** Fix released in agent v7.78. Workaround: downgrade to v7.71.2 or disable FIM.
- **Risk:** Long investigation (months). Initial theories about third-party AV interference were wrong. Required custom debug build for stack traces since Windows crash dumps weren't generated on clean stops.
- **Source:** SCRS-1914

### FIM custom rules not detecting files due to exact path matching (2026-03)

- **Symptoms:** Customer set up FIM to monitor `/var/www` directory but saw no events. Rules were loaded and CWS was healthy in the flare.
- **Product:** Workload Protection
- **Root cause:** The FIM rule expressions used the `in` operator with exact path matching (`chmod.file.path in ["/var/www"]`), which only matches operations on the directory entry itself, not on files within it.
- **Resolution:** Use the `=~` glob operator instead: `chmod.file.path =~ "/var/www/**"` to match files at any depth. Additional learnings: (1) `vim` triggers unlink syscalls during saves (temp file swap), use `process.file.name == "rm"` filter to distinguish real deletes; (2) `sudo` commands show `root` as user since CWS reports effective user at syscall time; (3) the `every: 5m0s` rate limiter suppresses duplicate events within the window.
- **Risk:** Common misconfiguration. The `in` operator for exact matching vs `=~` for glob matching is not obvious from the docs. Rate limiter can also cause confusion during testing.
- **Source:** SCRS-1986

### CWS FIM rule file extension syntax requires dot prefix (2026-02)

- **Symptoms:** Custom FIM rule for detecting file writes under `/var/www/` with extensions like `.php` shows `ACTIVITY: 0` and generates no security signal when tested with `touch /var/www/test.php`.
- **Product:** Workload Protection
- **Root cause:** Customer specified file extensions in the SECL rule without the leading dot (e.g., `"php"` instead of `".php"`). The `fim.write.file.extension` field requires the dot prefix.
- **Resolution:** Corrected the SECL rule syntax: `fim.write.file.extension in [ ".php", ".phar", ".ini", ".env", ".htaccess" ]` (note the dots). Documentation was unclear on this requirement.
- **Risk:** Easy to miss since the documentation doesn't explicitly show that the dot is required. The rule deploys without error but silently matches nothing.
- **Source:** SCRS-1950

### Duplicate cluster names cause CWS/CSPM config cycling (2026-03)

- **Symptoms:** Customer disabled CWS and CSPM in their DatadogAgent CRD, confirmed in Git/Flux/running pods, but audit trail showed config cycling between enabled and disabled every 2 minutes (800+ events/day). Only affected the dev cluster.
- **Product:** Workload Protection
- **Root cause:** Two different K8s clusters were configured with the same `clusterName: "dev-cluster"` and identical node names. Both clusters reported to the same Datadog org, causing conflicting agent config data to interleave. One cluster had security enabled, the other had it disabled, creating the appearance of cycling.
- **Resolution:** Assign a unique `spec.global.clusterName` to each cluster. Confirmed by graphing `datadog.agent.running` grouped by `orch_cluster_id` showing two distinct cluster IDs behind the same name.
- **Risk:** Duplicate cluster names with the same node names create extremely confusing debugging scenarios. `kubectl` commands on one cluster won't find the "ghost" pods visible in Datadog's UI. Always verify cluster name uniqueness across all environments.
- **Source:** SCRS-1967
