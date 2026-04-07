# Engineering Message: OOTB Anomaly Rule Silent Failure for Low-Activity Users

## For: `#k9-detection-engine-support`

---

**OOTB rule "Large amount of downloads on Google Drive" missed 34,917 unique downloads due to insufficient baseline (3 data points vs 10 minimum)**

A customer's OOTB anomaly rule (`o6k-nqg-bn1`, cardinality on `@event.parameters.doc_id`, grouped by `@usr.email`, `evaluationWindow: 1800`, `bucketDuration: 300`) did not generate a signal when a single user (`[customer-user@redacted]`) downloaded 34,917 unique files in a burst on March 25. No suppression rules match, logs are present in the SIEM index, and the cardinality is unambiguously anomalous.

**Root cause (confirmed via code):** The user had only 3 download events in the 8 days prior (Mar 18, Mar 19 x2). In `AnomalyPane.getBaseline()`, the non-seasonal baseline is fetched from `evalWindowStart - MAX_BASELINE_DURATION` (8 days) to `evalWindowStart`. After filtering NaNs, `baselineLen` was 3, which is below `MIN_BASELINE_ENTRY_COUNT` (10). `getBaseline()` returned null, `runAnomalyDetection()` returned empty, and no signal was generated.

Code path: `RuleReducerProcessor` -> log passes MLL check (3h10m < 7h) -> `AnomalyPane.consumeLogInternal` -> `addLog` buckets by `log.getEventTimestamp()` -> entry marked as changed -> `runPendingAnomalyDetection` -> `canRunAnomalyDetection` returns true (pane existed from prior activity, learning period met) -> `runAnomalyDetection` -> `getBaseline` returns null (3 < 10) -> no signal.

**The detection gap:** This OOTB rule silently fails for users with sparse activity (< 10 events in 8 days), which is arguably the highest-risk population for data exfiltration (compromised accounts, dormant insiders). The rule gives no indication that detection was skipped due to insufficient baseline. A user going from 3 downloads/week to 34,917 in a burst is exactly the scenario this rule is designed to catch.

**Questions for the team:**
1. Would it make sense to set `learningPeriodBaseline` on this OOTB rule as a fallback upper bound when baseline data is insufficient? The field exists in the code but is null on this rule.
2. Could `MIN_BASELINE_ENTRY_COUNT` be lowered for cardinality-based rules where even a small baseline is meaningful?
3. Is there appetite for a hybrid approach where the rule falls back to a static threshold when the anomaly baseline is insufficient?

We've advised the customer to create a complementary threshold rule in the meantime.

Refs: [AnomalyPane.java](https://github.com/DataDog/logs-backend/blob/6ec70c89ccdc2507653bcdc606c0f8b5b9f1dcdf/domains/cloud-security-platform/libs/core-reducer-aggregation/src/main/java/com/dd/logs/rule_engine/reducer/aggregation/AnomalyPane.java), [Anomaly detection eng doc](https://datadoghq.atlassian.net/wiki/spaces/CSiem/pages/2920940340)
