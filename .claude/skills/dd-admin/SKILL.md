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
- **Monitor Admin URL**: Parse org_id, monitor_id, cluster, time range (from_ts/to_ts are ms timestamps), and group_name from Monitor Admin URLs.
- **Watchdog Admin URL**: Parse org_id, bundle_id, and dc from Watchdog alert lifecycle URLs (format: `...watchdog-alert-lifecycle?org_id=<id>&bundle_id=<uuid>&dc=<dc>`).

## Cluster Derivation

The CLI auto-derives cluster from org_id using the `org_ranges` mapping in `config/dd-admin.yaml` (gitignored). Only use `--cluster` to override if the user specifies one explicitly.

## CLI Entry Points

### Monitor investigation

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

### Watchdog investigation

All commands go through `./box.sh dd-admin watchdog <subcommand>`:

```bash
# Bundle info — starting point (type, scope, status, signal key)
./box.sh dd-admin watchdog bundle <org_id> <bundle_id> [--dc <dc>]

# Signal history — anomaly timeline with values vs baseline
./box.sh dd-admin watchdog signals <org_id> <signal_key> [--dc <dc>]
```

`--dc` accepts the full datacenter domain (e.g. `us1.prod.dog`). Auto-derived from org_id if omitted.
`--shadow-name` passes an optional shadow pipeline name for shadow bundle reads.

#### Watchdog investigation workflow

0. **Discovery (if you only have an org_id)**: `watchdog find <org_id> [--status ONGOING] [--hours 24]`
   - Searches org 2 signal-bundler logs (needs `DD_API_KEY`/`DD_APP_KEY` with `logs_read` scope)
   - Returns all bundle_ids and signal_keys seen recently for that org — hand off to step 2/3
1. **Parse the URL** — if given a watchdog-alert-lifecycle URL, extract `org_id`, `bundle_id`, `dc`.
2. **Get bundle info**: `watchdog bundle <org_id> <bundle_id> --dc <dc>`
   - Shows type (e.g. `usm_latency_aggregate`), status (`ongoing`/`closed`), scope (service/env/operation/resource), and the **signal key** at the end.
3. **Get signal history**: `watchdog signals <org_id> <signal_key> --dc <dc>`
4. **Get full bundle lifecycle** (log-based, no VPN needed): `watchdog history <org_id> <bundle_id>`
   - Reconstructs the event timeline from signal-bundler audit logs: CREATED → SIGNAL_IN → PROPERTY_CHANGED → CLOSED/EXPIRED
   - Useful for understanding why a bundle is stuck, when it first appeared, how many signals it absorbed
   - Shows one line per history entry: timestamp, status, direction, anomaly window, anomalous value vs baseline (with multiplier), and the metric/anomaly queries at the bottom.

#### Key fields

| Field | Meaning |
|-------|---------|
| `status_name` | `ongoing` = still active; `closed` = resolved |
| `type` | Signal family: e.g. `usm_latency_aggregate`, `apm_latency_aggregate` |
| `direction` | `up` = latency/error spike; `down` = drop |
| `anomalous_value` vs `baseline_value` | Actual vs expected — multiplier shows severity |
| `signal_key` | ID to pass to `watchdog signals` |

---

#### Monitor investigation workflow

0. **Discovery (if you only have an org_id)**: `monitor find <org_id> [--hours 24]`
   - Searches org 2 alerting logs for recent state transitions (needs `DD_API_KEY`/`DD_APP_KEY` with `logs_read` scope)
   - Returns monitor_ids with transition type and timestamp — hand off to step 1

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
