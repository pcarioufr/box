"""Monitor Admin API client.

Wraps Datadog's internal Monitor Admin APIs (VPN-gated, no auth).
Used for debugging monitor evaluation during customer escalations.

Configuration is loaded from config/dd-admin.yaml (gitignored).
See config/example.dd-admin.yaml for the expected format.
"""

import json
import sys
from pathlib import Path

import requests
import yaml


# ── Config loading ───────────────────────────────────────────────────

_CONFIG = None
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "dd-admin.yaml"
EXAMPLE_PATH = Path(__file__).parent.parent.parent / "config" / "example.dd-admin.yaml"


def _load_config() -> dict:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    if not CONFIG_PATH.exists():
        print(
            f"Error: config/dd-admin.yaml not found.\n"
            f"Copy config/example.dd-admin.yaml to config/dd-admin.yaml and fill in your values.",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        _CONFIG = yaml.safe_load(f)
    return _CONFIG


def _monitor_config() -> dict:
    return _load_config()["monitor_admin"]


def _clusters() -> dict:
    return _monitor_config()["clusters"]


def _evaluator_pool(monitor_type_id: int) -> str:
    pools = _monitor_config().get("evaluator_pools") or {}
    return pools.get(str(monitor_type_id)) or pools.get(monitor_type_id) or pools["default"]


# ── Constants (non-sensitive) ────────────────────────────────────────

STATUS_MAP = {
    0: "OK", 1: "ALERT", 2: "WARNING", 3: "NO_DATA",
    4: "SKIPPED", 10: "OK_STAY_ALERT",
}
STATUS_CODE_MAP = {v: k for k, v in STATUS_MAP.items()}

COMPARATOR_SYMBOLS = {
    "GE": ">=", "GT": ">", "LE": "<=", "LT": "<", "EQ": "==",
}


# ── Cluster derivation ──────────────────────────────────────────────

def cluster_from_org_id(org_id: str) -> str:
    """Derive cluster from org_id based on configured ranges."""
    n = int(org_id)
    for entry in _monitor_config()["org_ranges"]:
        min_id = entry.get("min_org_id", 0)
        max_id = entry.get("max_org_id")
        if n >= min_id and (max_id is None or n < max_id):
            return entry["cluster"]
    raise ValueError(f"No cluster mapping found for org_id {org_id}")


# ── API ──────────────────────────────────────────────────────────────

def api_call(cluster: str, path: str, body: dict) -> dict:
    """POST to a Monitor Admin API endpoint."""
    clusters = _clusters()
    host = clusters.get(cluster)
    if not host:
        raise ValueError(f"Unknown cluster: {cluster}. Valid: {', '.join(clusters)}")
    resp = requests.post(
        f"https://{host}{path}",
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def format_status_counts(counts: dict) -> str:
    return ", ".join(
        f"{STATUS_MAP.get(int(k), f'STATUS_{k}')}: {v}"
        for k, v in counts.items()
    )


# ── Commands ─────────────────────────────────────────────────────────

def get_state(cluster: str, org_id: str, monitor_id: str) -> str:
    """Get current monitor state and all group statuses."""
    data = api_call(cluster, "/v1/monitor_states/get", {
        "monitorId": monitor_id, "orgId": org_id,
    })
    from datetime import datetime, timezone
    groups = list((data.get("groups") or {}).values())
    lines = [
        f"Monitor {monitor_id} (org {org_id}) on {cluster}",
        f"Overall State: {data.get('overallState')}",
        f"State Map: {json.dumps(data.get('stateMap'))}",
        f"Total Groups: {data.get('numGroups')}",
        f"Last Result: {datetime.fromtimestamp(int(data.get('last_result_ts', 0)), tz=timezone.utc).isoformat()}",
        f"State Modified: {data.get('overall_state_modified')}",
        "",
        "Groups with non-OK status or forced reasons:",
    ]
    interesting = [
        g for g in groups
        if g.get("status") != "OK"
        or g.get("forced_status_reason") != "none"
        or g.get("removed_ts")
    ]
    if not interesting:
        lines.append("  (all groups OK, no forced statuses)")
    else:
        for g in interesting:
            line = f"  {g['name']}: {g['status']}"
            if g.get("forced_status_reason") != "none":
                line += f" (forced: {g['forced_status_reason']})"
            if g.get("removed_ts"):
                line += f" (removed: {datetime.fromtimestamp(int(g['removed_ts']), tz=timezone.utc).isoformat()})"
            lines.append(line)
    return "\n".join(lines)


def get_results(cluster: str, org_id: str, monitor_id: str, from_ts: str, to_ts: str) -> str:
    """List all evaluations in a time range."""
    from datetime import datetime, timezone
    data = api_call(cluster, "/v1/monitor_results/get_from_timerange", {
        "from": from_ts, "to": to_ts,
        "monitor_id": monitor_id, "org_id": org_id,
    })
    results = data.get("results") or []
    lines = [
        f"Monitor {monitor_id} results from {from_ts} to {to_ts}",
        f"Total results: {len(results)}",
        "",
    ]
    for r in results:
        res = r["result"]
        meta = r["metadata"]
        eval_ts = datetime.fromtimestamp(int(res["evaluation_timestamp"]), tz=timezone.utc).isoformat()
        sched_ts = datetime.fromtimestamp(int(res["scheduled_timestamp"]), tz=timezone.utc).isoformat()
        has_error = res.get("eval_error") and len(res["eval_error"]) > 0
        line = (
            f"Result {res['result_id']} | eval: {eval_ts} | sched: {sched_ts}"
            f" | {format_status_counts(meta.get('status_counts', {}))}"
            f" | dist: {meta.get('distribution_factor')}"
        )
        if has_error:
            line += f" | ERROR: {json.dumps(res['eval_error'])}"
        lines.append(line)
    return "\n".join(lines)


def get_result_detail(
    cluster: str, org_id: str, result_id: str, timestamp: str,
    group_filter: str = None, status_filter: list[str] = None,
) -> str:
    """Get detailed per-group values, thresholds, and margins for one evaluation."""
    data = api_call(cluster, "/v1/monitor_results/get", {
        "id": result_id, "org_id": org_id, "timestamp": timestamp,
    })
    sched = (data.get("result") or {}).get("scheduling_result") or {}
    eval_result = sched.get("evaluation_result") or {}
    groups = list(eval_result.get("groups") or [])

    monitor = sched.get("monitor") or {}
    query_info = eval_result.get("parsed_monitor_query_info") or {}
    query_debug = (eval_result.get("debug") or {}).get("content", {}).get("query")
    comparator = query_info.get("comparator", "unknown")
    comp_symbol = COMPARATOR_SYMBOLS.get(comparator, comparator)

    # Filters
    if group_filter:
        groups = [g for g in groups if group_filter in g.get("name", "")]
    if status_filter:
        codes = {STATUS_CODE_MAP[s] for s in status_filter if s in STATUS_CODE_MAP}
        groups = [g for g in groups if (g.get("status") or 0) in codes]

    lines = []
    if monitor.get("name"):
        lines.append(f"Monitor: {monitor['name']} (ID: {monitor.get('id')})")
    if query_debug:
        lines.append(f"Query: {query_debug}")
    if query_info.get("metrics"):
        lines.append(f"Metrics: {', '.join(query_info['metrics'])}")
    lines.append(f"Comparator: {comp_symbol} (triggers when value {comp_symbol} threshold)")
    if query_info.get("timeframe"):
        lines.append(f"Timeframe: {query_info['timeframe']}")
    lines.append("")
    lines.append(f"Result {result_id} detail ({len(groups)} groups shown)")
    lines.append("")

    for g in groups:
        status = STATUS_MAP.get(g.get("status") or 0, f"STATUS_{g.get('status')}")
        line = f"  {g.get('name')}: {status}"
        if g.get("value") is not None:
            line += f" | value: {g['value']}"
        sd = (g.get("details") or {}).get("snapshot_data")
        if sd:
            line += f" | threshold: {sd.get('threshold')}"
            if g.get("value") is not None and sd.get("threshold") is not None:
                margin = sd["threshold"] - g["value"]
                pct = f"{(margin / sd['threshold'] * 100):.1f}" if sd["threshold"] != 0 else "N/A"
                line += f" | margin: {'+' if margin >= 0 else ''}{margin:.4f} ({pct}% of threshold)"
            if sd.get("critical_recovery_threshold") is not None:
                line += f" | recovery: {sd['critical_recovery_threshold']}"
            line += f" | window: {sd.get('from_ts')} -> {sd.get('to_ts')}"
        if g.get("last_seen"):
            line += f" | last_seen: {g['last_seen']}"
        lines.append(line)
    return "\n".join(lines)


def get_group_payload(
    cluster: str, org_id: str, monitor_id: str, group_filter: str = None,
) -> str:
    """Get alert history for monitor groups."""
    from datetime import datetime, timezone
    data = api_call(cluster, "/v1/monitor_states/get_payload", {
        "monitorId": monitor_id, "orgId": org_id,
    })
    groups = data.get("groups") or []
    if group_filter:
        groups = [g for g in groups if group_filter in g.get("name", "")]

    interesting = [
        g for g in groups
        if g.get("last_triggered_ts") or g.get("last_resolved_ts") or g.get("removed_ts")
    ]
    lines = [
        f"Monitor {monitor_id} group payload ({len(interesting)} groups with history, {len(groups)} total)",
        "",
    ]
    for g in interesting:
        parts = [f"  {g['name']}"]
        for field, label in [
            ("last_triggered_ts", "triggered"),
            ("last_resolved_ts", "resolved"),
            ("last_notified_ts", "notified"),
            ("first_triggered_ts", "first_triggered"),
            ("removed_ts", "removed"),
        ]:
            if g.get(field):
                parts.append(f"{label}: {datetime.fromtimestamp(int(g[field]), tz=timezone.utc).isoformat()}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def reevaluate(
    cluster: str, org_id: str, result_id: str, timestamp: str,
    group_filter: str = None,
) -> str:
    """Re-evaluate a past result with current data to diagnose late-arriving data."""
    # Fetch original
    original = api_call(cluster, "/v1/monitor_results/get", {
        "id": result_id, "org_id": org_id, "timestamp": timestamp,
    })
    sched = (original.get("result") or {}).get("scheduling_result") or {}
    monitor_obj = sched.get("monitor")
    if not monitor_obj:
        raise ValueError("Could not retrieve monitor object from original result")

    orig_groups = (sched.get("evaluation_result") or {}).get("groups") or []
    monitor_type_id = monitor_obj.get("monitor_type_id")
    evaluator_pool = _evaluator_pool(monitor_type_id)

    # Re-evaluate
    reeval = api_call(cluster, "/v1/monitor_results/reevaluate", {
        "timestamp": timestamp,
        "monitor": monitor_obj,
        "org_id": org_id,
        "evaluator_pool": evaluator_pool,
    })
    new_result = reeval.get("result") or {}
    new_groups = new_result.get("evaluation_result", {}).get("groups") or new_result.get("groups") or []

    lines = [
        f"Re-evaluation of result {result_id} at {timestamp}",
        f"Monitor: {monitor_obj.get('name') or monitor_obj.get('id')} (type: {monitor_type_id})",
        f"Evaluator: {evaluator_pool}",
        "",
        "Comparison (original → re-evaluated):",
        "",
    ]
    orig_by_name = {g["name"]: g for g in orig_groups}

    filtered = new_groups
    if group_filter:
        filtered = [g for g in filtered if group_filter in g.get("name", "")]

    for ng in filtered:
        og = orig_by_name.get(ng.get("name"))
        orig_status = STATUS_MAP.get(og.get("status") or 0, f"STATUS_{og.get('status')}") if og else "N/A"
        new_status = STATUS_MAP.get(ng.get("status") or 0, f"STATUS_{ng.get('status')}")
        orig_val = og.get("value", "N/A") if og else "N/A"
        new_val = ng.get("value", "N/A")
        changed = orig_val != new_val or orig_status != new_status
        marker = " ← CHANGED" if changed else ""
        lines.append(f"  {ng.get('name')}: {orig_status} ({orig_val}) → {new_status} ({new_val}){marker}")

    # Show original groups missing from re-evaluation
    if not group_filter:
        new_names = {g.get("name") for g in new_groups}
        for og in orig_groups:
            if og.get("name") not in new_names:
                orig_status = STATUS_MAP.get(og.get("status") or 0, f"STATUS_{og.get('status')}")
                lines.append(f"  {og['name']}: {orig_status} ({og.get('value')}) → MISSING in re-evaluation")

    return "\n".join(lines)


def downtime_search(cluster: str, org_id: str, query: str, size: int = 50) -> str:
    """Search for downtimes that may affect a monitor."""
    data = api_call(cluster, "/v1/monitor_results/downtime_search", {
        "org_id": org_id, "query": query, "size": size, "from": 0,
    })
    lines = [f'Downtime search for "{query}" (total: {(data.get("total") or {}).get("value", 0)})', ""]
    downtimes = data.get("downtimes") or []
    if not downtimes:
        lines.append("  No downtimes found.")
    else:
        for d in downtimes:
            lines.append(f"  {json.dumps(d)}")
    return "\n".join(lines)
