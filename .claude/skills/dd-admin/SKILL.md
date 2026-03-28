---
name: dd-admin
description: Investigate monitor triggering issues using Datadog's internal Monitor Admin APIs. Use when debugging why a monitor triggered, didn't trigger, or has unexpected state. Requires VPN. Input should include org_id, monitor_id, time range, and optionally a group query.
---

# DD Admin — Monitor Investigation

Investigate monitor evaluation issues for customer escalations using internal Monitor Admin APIs.

## Prerequisites

- **Datadog VPN** must be connected (APIs are VPN-gated, no auth tokens needed)

## Input Parsing

The user will provide some combination of:
- **org_id**: Customer organization ID (numeric)
- **monitor_id**: Monitor being investigated (numeric)
- **time range**: When the issue occurred — convert to **UTC ISO 8601** before calling CLI
- **group query**: Optional group to focus on (e.g., `jet_tenant:de,statuscode:503`)
- **Monitor Admin URL**: Parse org_id, monitor_id, cluster, time range (from_ts/to_ts are ms timestamps), and group_name from URLs like `https://monitor-admin.eu1.prod.dog/monitors/cluster/realtime/org/{org_id}/monitor/{monitor_id}?from_ts=...&to_ts=...&group_name=...`

## Cluster Derivation

The CLI auto-derives cluster from org_id. Only use `--cluster` to override if the user specifies one.

| Cluster | Org ID Range |
|---------|-------------|
| us1 | < 1,000,000,000 |
| eu1 | 1,000,000,000 – 1,099,999,999 |
| us1_fed | 1,100,000,000 – 1,199,999,999 |
| us3 | 1,200,000,000 – 1,299,999,999 |
| us5 | 1,300,000,000 – 1,399,999,999 |
| ap1 | >= 1,400,000,000 |

For org_ids >= 1.4B, ask the user to confirm the cluster.

## CLI Entry Points

All commands go through `./box.sh dd-admin monitor <subcommand>`:

```bash
# Current state
./box.sh dd-admin monitor state <org_id> <monitor_id>

# Evaluation results in a time range
./box.sh dd-admin monitor results <org_id> <monitor_id> --from <ISO8601> --to <ISO8601>

# Detailed per-group values for one evaluation
./box.sh dd-admin monitor detail <org_id> <result_id> --timestamp <ISO8601> [--group <filter>] [--status OK,ALERT,...]

# Alert history (triggered/resolved timestamps)
./box.sh dd-admin monitor payload <org_id> <monitor_id> [--group <filter>]

# Re-evaluate with current data (late-data diagnosis)
./box.sh dd-admin monitor reevaluate <org_id> <result_id> --timestamp <ISO8601> [--group <filter>]

# Search downtimes
./box.sh dd-admin monitor downtimes <org_id> <query> [--size 50]
```

## Investigation Workflow

### Step 1: Get current monitor state
Use `monitor state` to understand the current state.
- How many groups? What is overall state?
- Any non-OK groups or forced statuses (e.g., `new_group_delay`)?

### Step 2: Get evaluation results for the time range
Use `monitor results` to list all evaluations during the period.
- Look at status counts per evaluation (OK, ALERT, WARNING, SKIPPED, OK_STAY_ALERT)
- Check for evaluation errors
- Identify when status transitions happened

### Step 3: Drill into specific evaluations and analyze margin
Use `monitor detail` for key evaluation timestamps (especially around transitions).
- **This is the most important step** — shows actual **value** vs **threshold** per group
- Returns the **monitor query**, **name**, and **comparator** (e.g., `>=`)
- **Margin analysis**: how far from threshold (absolute + % of threshold)
  - **Positive margin**: below threshold (not triggering) — larger = safer
  - **Negative margin**: exceeded threshold (triggered) — more negative = bigger overshoot
  - **Small margin** (±5%): borderline / potentially noisy

### Step 4: Check alert history if needed
Use `monitor payload` to see triggered/resolved/notified timestamps.

### Step 5: Check downtimes if relevant
Use `monitor downtimes` if the monitor may have been silenced.

### Step 6: Re-evaluate if data contradicts the result
If the evaluation seems inconsistent (triggered but values look fine, or vice versa), use `monitor reevaluate`.

It re-runs the evaluation with data available *now* and compares to the original. If results differ (`← CHANGED`), late-arriving data is the explanation.

**When to re-evaluate**: any question like "why did it trigger while it looks green?" or "why didn't it trigger while it looks red?" — always re-evaluate before concluding.

## Status Codes

| Code | Name | Meaning |
|------|------|---------|
| 0 | OK | Below threshold |
| 1 | ALERT | Exceeds critical threshold |
| 2 | WARNING | Exceeds warning threshold |
| 3 | NO_DATA | No data received |
| 4 | SKIPPED | Not enough data points |
| 10 | OK_STAY_ALERT | Recovered but recovery conditions not yet met |

## Output Format

Provide a clear summary:
1. **Monitor definition**: query, metric, comparator, threshold
2. **Current state**: overall status
3. **Timeline**: what happened during the investigated period
4. **Root cause**: why it triggered (or didn't) — cite value vs threshold
5. **Margin analysis**: how close/far from threshold, trend across evaluations
6. **Late data check**: if data contradicts the decision, report re-evaluation results

Be precise with numbers. Always show actual value, threshold, and margin.

$ARGUMENTS
