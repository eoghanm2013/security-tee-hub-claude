# Cloud SIEM Signal Mechanics: What TSEs Need to Know

> **Revision:** March 2026
> **Audience:** TSEs working Cloud SIEM signal-related tickets
> **Author:** TEE team
> **Source investigation:** SCRS-2029
> **Confidence:** Everything in this doc is confirmed from source code (`DataDog/logs-backend`), documentation, engineering input, or live reproduction. Nothing is inferred.

---

## 1. Ingestion Time vs Event Time

**The single biggest source of confusion in Cloud SIEM signal tickets.**

The detection engine evaluates logs by **ingestion time** (when Datadog receives the log). The UI (RULE DETAILS, signal window, Related Logs) displays logs by **event time** (the timestamp inside the log, e.g. CloudTrail `eventTime`).

**Confirmed from:** Source code (signal constructor, pane evaluation), engineering confirmation (SCRS-709, Clement Gaboriaucouanau), live reproduction.

Typical delivery lags:

| Log Source | Typical Lag |
|---|---|
| AWS CloudTrail | 2-15 minutes |
| AWS GuardDuty | 5-15 minutes |
| GCP Audit Logs | 1-5 minutes |
| Azure Activity Logs | 1-10 minutes |

**What this looks like:** A signal fires at 13:04 based on a log with `eventTime` 13:10. RULE DETAILS queries by event time and shows zero matches for that log. The customer sees "no matching logs" and thinks it's a false positive. It's not.

**How to verify:** Check the signal's severity against the rule's case order. Cases evaluate top-down, first match wins. If the signal is HIGH but RULE DETAILS only shows matches for the MEDIUM case, then the HIGH case's query necessarily matched at evaluation time. The severity is proof.

---

## 2. Severity Promotion During Keep-Alive

When a signal is open (during keep-alive), the engine continues evaluating incoming logs. If a **higher-priority rule case** is satisfied, the signal's severity is **promoted**. It is never demoted.

**Confirmed from:** Source code (`EntriesPane.updateSignal()`: `if (matchingRuleCaseIndex < existingSignal.getRuleCaseIndex())` promotes and logs `"Increasing the severity of signal"`), live reproduction.

**What this looks like:**
1. Exception logs arrive, Case 2 (MEDIUM) fires, signal created as MEDIUM
2. Success log arrives during keep-alive, Case 1 (HIGH) now matches
3. Engine promotes the signal from MEDIUM to HIGH
4. RULE DETAILS still shows the original evaluation window where only exceptions matched
5. The success log is invisible in RULE DETAILS if its event time is outside the displayed window

**Reproduced:** We created a rule with eval=5min, keepAlive=5min, maxDuration=5min. Sent exception logs, waited 6.5 minutes, sent a success log with a backdated event timestamp (simulating CloudTrail lag). Result: HIGH signal with zero success in RULE DETAILS. Exact match to SCRS-2029.

---

## 3. Sample Log Overwrite

When a signal is updated (e.g. during severity promotion), the engine replaces per-query sample logs with newer ones.

**Confirmed from:** Source code (`Signal.updateSamples()`: replaces sample when `newSample.getEventTimestamp() > existing.getEventTimestamp()`).

**What this looks like:** Signal 1's "trigger" or sample in the UI shows a log that has an event time outside the signal's displayed window. This is because the sample was overwritten during a keep-alive update with a newer log. The original triggering log is no longer visible.

---

## 4. Related Logs Are Entity-Scoped

Related Logs query by the signal's **group-by attributes** (e.g. `userIdentity.arn`, user ID, IP) over a broader time range. They are NOT scoped to the detection window.

**Confirmed from:** Documentation ([Sample Logs in SIEM](https://datadoghq.atlassian.net/wiki/spaces/CSiem/pages/5444044149)).

**What this looks like:** Customer sees logs in Related Logs with timestamps outside the signal window and assumes they triggered the signal. They didn't, they're just contextual logs for the same entity.

**Fallback behavior:** When original triggering logs expire from retention, Related Logs falls back to showing the saved sample log.

---

## 5. Keep-Alive Is Dynamic, Not a Fixed Timer

There is no explicit timer that counts down and "resets." Keep-alive is computed dynamically on each evaluation:

```
endOfSignal = min(lastSeen + keepAlive, firstSeen + maxSignalDuration)
```

Each log that extends `lastSeen` shifts the keep-alive window forward. `firstSeen + maxSignalDuration` is the hard cap.

**Confirmed from:** Source code (`GenericPane.findSignalAroundDate()`), live reproduction.

**Reproduced:** With keepAlive=5min and maxSignalDuration=5min, continuous exception logs (sent every 60s) kept the signal alive past the theoretical hard cap of `firstSeen + 5min`. The signal accepted a success log ingested 6.5 minutes after `firstSeen`.

---

## 6. RULE DETAILS Only Shows Event-Time-Scoped Matches

RULE DETAILS queries logs whose **event time** falls within the signal's displayed window. Logs processed by the engine during keep-alive but with event times outside the window are invisible in RULE DETAILS.

**Confirmed from:** Live reproduction. We sent 47 exception logs total (5 initial + 12 trickle + 30 burst). Only 15 appeared in RULE DETAILS, those whose event times fell within the 5-min evaluation window. The other 32 (with event times outside the window) were absorbed by the engine but invisible in RULE DETAILS.

---

## 7. Signal Timestamps

| Timestamp | Source | Used For |
|---|---|---|
| `creationDate` (UI display time) | Triggering log's **ingestion time** | Signal list, signal header |
| `firstSeen` | **Event time** of earliest matching log | Evaluation window start |
| `lastSeen` | **Event time** of latest matching log (capped by maxSignalDuration) | Keep-alive calculation |

**Confirmed from:** Source code (`Signal` constructor: `creationDate = triggeringLogIngestionDate`; `firstSeen`/`lastSeen` from event time deltas).

---

## 8. Playbook Re-Rendering

The Playbook message is **re-rendered from the signal's current state** every time the signal is output. It is not a static snapshot from creation time.

After severity promotion, template variables reflect both the original data and any new data from the promotion event. Projections (attribute values) are merged progressively via `mergeEntryIntoProjection()`.

**Confirmed from:** Source code (`AbstractSignalOutput.getMessage()` renders Handlebars template against `getTemplateValues()` which pulls from the signal's current state).

---

## Quick Reference

| Customer Says | Root Cause | Section |
|---|---|---|
| "Signal is HIGH but RULE DETAILS shows no matching logs" | Ingestion time vs event time + severity promotion | 1, 2 |
| "Related Logs shows events outside the signal window" | Entity-scoped, not window-scoped | 4 |
| "Why didn't my signal re-trigger?" | No qualifying logs during keep-alive | 5 |
| "RULE DETAILS count doesn't match Log Explorer" | RULE DETAILS queries event time; engine uses ingestion time | 1, 6 |
| "Playbook shows data that doesn't match RULE DETAILS" | Playbook updated during keep-alive; RULE DETAILS shows original window | 2, 8 |
| "The trigger log has a timestamp outside the signal window" | Sample overwritten during keep-alive update | 3 |

---

## Internal References

| Resource | Covers |
|---|---|
| [Anatomy of a Detection Rule](https://datadoghq.atlassian.net/wiki/spaces/TS/pages/3054505811) | Detection rule types, pane evaluation, signal generation |
| [Signal Keep Alive vs Max Signal Duration](https://datadoghq.atlassian.net/wiki/spaces/~621fcdba49c90000701f5e03/pages/4392747930) | Keep-alive mechanics with diagrams |
| ["Sample Logs" in SIEM](https://datadoghq.atlassian.net/wiki/spaces/CSiem/pages/5444044149) | How sample logs and fallback work |
| [SCRS-709](https://datadoghq.atlassian.net/browse/SCRS-709) | Engineering confirmation of ingestion time vs event time |
| [SCRS-2029](https://datadoghq.atlassian.net/browse/SCRS-2029) | Source investigation for this document |
| Source code: `DataDog/logs-backend` | `domains/cloud-security-platform/libs/core-reducer-aggregation/` |

## Public Docs for Customers

- [Cloud SIEM Detection Rules](https://docs.datadoghq.com/security/cloud_siem/detection_rules/)
- [Investigate Security Signals](https://docs.datadoghq.com/security/cloud_siem/triage_and_investigate/investigate_security_signals)
