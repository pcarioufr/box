"""Log-based discovery for monitor and Watchdog investigations.

Queries org 2's Datadog logs to find bundle_ids / monitor_ids for a customer
org — without needing a specific ID to start from. Uses the same DD_API_KEY /
DD_APP_KEY env vars as the rest of the Datadog CLI.

Key log sources:
  - service:signal-bundler  → Watchdog bundle lifecycle, all customer orgs
  - service:alerting*       → Monitor transitions, all customer orgs
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_list_request import LogsListRequest
from datadog_api_client.v2.model.logs_list_request_page import LogsListRequestPage
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter
from datadog_api_client.v2.model.logs_sort import LogsSort


def _dd_config() -> Configuration:
    api_key = os.getenv("DD_API_KEY")
    app_key = os.getenv("DD_APP_KEY")
    if not api_key or not app_key:
        print(
            "Error: DD_API_KEY and DD_APP_KEY must be set.\n"
            "These should be org 2 (Datadog internal) API keys.",
            file=sys.stderr,
        )
        sys.exit(1)
    cfg = Configuration()
    cfg.api_key["apiKeyAuth"] = api_key
    cfg.api_key["appKeyAuth"] = app_key
    return cfg


def _search_logs(query: str, from_ts: datetime, to_ts: datetime, limit: int = 300) -> list[dict]:
    """Return raw log events matching query in the given time window."""
    cfg = _dd_config()
    results = []
    cursor = None

    with ApiClient(cfg) as client:
        api = LogsApi(client)
        while True:
            page = LogsListRequestPage(limit=min(limit - len(results), 1000))
            if cursor:
                page = LogsListRequestPage(limit=min(limit - len(results), 1000), cursor=cursor)
            req = LogsListRequest(
                filter=LogsQueryFilter(
                    query=query,
                    _from=from_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    to=to_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
                sort=LogsSort.TIMESTAMP_DESCENDING,
                page=page,
            )
            resp = api.list_logs(body=req)
            for event in resp.data or []:
                results.append({
                    "timestamp": event.attributes.timestamp if event.attributes else None,
                    "message": event.attributes.message if event.attributes else "",
                    "attributes": dict(event.attributes.attributes) if (event.attributes and event.attributes.attributes) else {},
                })
            meta = resp.meta
            page = getattr(meta, "page", None) if meta else None
            if not page or not getattr(page, "after", None) or len(results) >= limit:
                break
            cursor = page.after

    return results


def _ts(epoch: int | None) -> str:
    if not epoch:
        return "?"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Watchdog bundle discovery ─────────────────────────────────────────

def find_watchdog_bundles(
    org_id: str,
    hours: int = 24,
    status_filter: str | None = None,
) -> str:
    """Find Watchdog bundles for a customer org from signal-bundler audit logs."""
    now = datetime.now(timezone.utc)
    from_ts = now - timedelta(hours=hours)

    query = f'service:signal-bundler "json_audit_log" @org_id:{org_id}'

    print(f"[searching signal-bundler logs for org {org_id} over last {hours}h...]", file=sys.stderr)
    logs = _search_logs(query, from_ts, now, limit=500)

    # Deduplicate by bundle_id — keep most recent state per bundle
    bundles: OrderedDict[str, dict] = OrderedDict()
    for log in reversed(logs):  # oldest first so latest overwrites
        msg = log.get("message", "")
        if "json_audit_log" not in msg:
            continue
        try:
            raw = msg[msg.index("{"):]
            data = json.loads(raw)
            for b in data.get("Bundle", []):
                bid = b.get("id")
                if bid:
                    bundles[bid] = {
                        "bundle_id": bid,
                        "type": b.get("type", "?"),
                        "status": b.get("status", "?"),
                        "org_id": b.get("org_id"),
                        "is_frontend_worthy": b.get("is_frontend_worthy"),
                        "is_alert_worthy": b.get("is_alert_worthy"),
                        "latest_signal_key": b.get("latest_signal_key"),
                        "first_epoch": b.get("first_epoch"),
                        "last_epoch": b.get("last_epoch"),
                        "num_aggregates": b.get("num_aggregates", 0),
                        "last_seen": log.get("timestamp"),
                    }
        except (ValueError, json.JSONDecodeError, KeyError):
            continue

    if status_filter:
        bundles = OrderedDict(
            (k, v) for k, v in bundles.items()
            if v["status"].upper() == status_filter.upper()
        )

    if not bundles:
        return f"No Watchdog bundles found for org {org_id} in the last {hours}h."

    lines = [
        f"Watchdog bundles for org {org_id} (last {hours}h, {len(bundles)} found)",
        "",
    ]
    for b in bundles.values():
        status = b["status"]
        worthy = "frontend" if b["is_frontend_worthy"] else ("alert" if b["is_alert_worthy"] else "internal")
        lines.append(
            f"{'[ONGOING]' if status == 'ONGOING' else '[RESOLVED]'} "
            f"{b['bundle_id']}  type={b['type']}  aggs={b['num_aggregates']}  worthy={worthy}"
        )
        lines.append(
            f"  window: {_ts(b['first_epoch'])} → {_ts(b['last_epoch'])}"
        )
        if b["latest_signal_key"]:
            lines.append(f"  signal_key: {b['latest_signal_key']}  ← use with 'watchdog signals'")
        lines.append("")

    return "\n".join(lines).rstrip()


# ── Bundle history ───────────────────────────────────────────────────

# Maps function_call.name to a human-readable lifecycle event label
_LIFECYCLE = {
    "__init__":                       "CREATED",
    "add_aggregate":                  "SIGNAL_IN",
    "update_existing_aggregate":      "SIGNAL_UPDATED",
    "_update_bundle_data_from_aggregate": "BUNDLE_UPDATED",
    "observe_change":                 "PROPERTY_CHANGED",
    "close":                          "CLOSED",
    "expire":                         "EXPIRED",
}


_DELTA_FLAGS = ["is_event_worthy", "is_frontend_worthy", "is_wd_story_valid", "is_alert_worthy"]


def get_bundle_history(
    org_id: str,
    bundle_id: str,
    hours: int = 48,
    from_ts: str | None = None,
    to_ts: str | None = None,
    verbose: bool = False,
) -> str:
    """Reconstruct the full lifecycle of a bundle from signal-bundler audit logs."""
    now = datetime.now(timezone.utc)
    if from_ts:
        dt_from = datetime.fromisoformat(from_ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    else:
        dt_from = now - timedelta(hours=hours)
    if to_ts:
        dt_to = datetime.fromisoformat(to_ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    else:
        dt_to = now

    window_desc = (
        f"{dt_from.strftime('%Y-%m-%dT%H:%M:%SZ')} → {dt_to.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        if from_ts or to_ts
        else f"last {hours}h"
    )

    # Bundle ID appears in the message description for all its events
    query = f'service:signal-bundler "json_audit_log" @org_id:{org_id} "{bundle_id}"'

    print(f"[searching signal-bundler logs for bundle {bundle_id} (org {org_id}), window: {window_desc}...]",
          file=sys.stderr)
    LIMIT = 500
    logs = _search_logs(query, dt_from, dt_to, limit=LIMIT)
    hit_cap = len(logs) >= LIMIT

    if not logs:
        return f"No log events found for bundle {bundle_id} (org {org_id}) in {window_desc}."

    # Parse and sort oldest-first for timeline
    events = []
    for log in logs:
        msg = log.get("message", "")
        if "json_audit_log" not in msg or bundle_id not in msg:
            continue
        try:
            raw = msg[msg.index("{"):]
            data = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            continue

        fn = (data.get("function_call") or {}).get("name", "?")
        description = data.get("description", "")
        bundle_snap = (data.get("Bundle") or [{}])[0]

        ts = log.get("timestamp")
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(ts, "strftime") else str(ts)

        events.append({
            "ts": ts_str,
            "fn": fn,
            "label": _LIFECYCLE.get(fn, fn),
            "description": description,
            "status": bundle_snap.get("status"),
            "num_aggregates": bundle_snap.get("num_aggregates"),
            "type": bundle_snap.get("type"),
            "is_closed": bundle_snap.get("is_closed"),
            "first_epoch": bundle_snap.get("first_epoch"),
            "last_epoch": bundle_snap.get("last_epoch"),
            "latest_signal_key": bundle_snap.get("latest_signal_key"),
            "is_event_worthy": bundle_snap.get("is_event_worthy"),
            "is_frontend_worthy": bundle_snap.get("is_frontend_worthy"),
            "is_wd_story_valid": bundle_snap.get("is_wd_story_valid"),
            "is_alert_worthy": bundle_snap.get("is_alert_worthy"),
            "raw_data": data if verbose else None,
        })

    if not events:
        return f"No parseable events found for bundle {bundle_id}."

    # Sort oldest first
    events.sort(key=lambda e: e["ts"])

    lines = [
        f"Bundle history: {bundle_id}  (org {org_id}, {len(events)} events, {window_desc})",
        "",
    ]
    if hit_cap:
        first_ts = events[0]["ts"] if events else "?"
        lines.append(
            f"⚠ {LIMIT}-event cap reached — events before {first_ts} not shown."
            f" Use --from/--to to target a narrower window."
        )
        lines.append("")

    prev_status = None
    prev_flags: dict = {}
    for e in events:
        label = e["label"]
        status = e["status"] or "?"
        status_change = f"  [{prev_status} → {status}]" if prev_status and status != prev_status else ""
        prev_status = status

        line = f"[{e['ts']}]  {label:20s}  status={status}{status_change}"

        if label == "SIGNAL_IN":
            line += f"  aggs={e['num_aggregates']}  type={e['type']}"
            if e.get("latest_signal_key"):
                line += f"  signal_key={e['latest_signal_key']}"
        elif label == "PROPERTY_CHANGED":
            changed = e["description"].replace(f"Bundle {bundle_id} has updated property ", "")
            line += f"  {changed}"
        elif label in ("CLOSED", "EXPIRED"):
            window = f"{_ts(e['first_epoch'])} → {_ts(e['last_epoch'])}"
            line += f"  window={window}  aggs={e['num_aggregates']}"
        elif label == "CREATED":
            line += f"  type={e['type']}"

        # Delta annotations for key boolean flags — show on first appearance and on change
        for field in _DELTA_FLAGS:
            val = e.get(field)
            if val is None:
                continue
            if field not in prev_flags:
                line += f"  {field}={val}"
            elif val != prev_flags[field]:
                line += f"  {field}: {prev_flags[field]}→{val}"
            prev_flags[field] = val

        lines.append(line)

        if verbose and e.get("raw_data"):
            raw_json = json.dumps(e["raw_data"], default=str, indent=2)
            lines.append("  " + raw_json.replace("\n", "\n  "))
            lines.append("")

    # Summary
    last = events[-1]
    lines += [
        "",
        f"Final state:  status={last['status']}  type={last['type']}  "
        f"aggs={last['num_aggregates']}  closed={last['is_closed']}",
        f"Window:       {_ts(last['first_epoch'])} → {_ts(last['last_epoch'])}",
    ]
    if last.get("latest_signal_key"):
        lines.append(f"Signal key:   {last['latest_signal_key']}  ← use with 'watchdog signals'")

    return "\n".join(lines)


# ── Monitor transition discovery ──────────────────────────────────────

_TRANSITION_RE = re.compile(
    r"org_id=(\d+)\s+monitor_id=(\d+)\s+result_id=(\d+).*?transition_type=(\S+)"
)
_NOTIFY_RE = re.compile(
    r"org_id=(\d+)\s+monitor_id=(\d+)"
)


def find_monitor_transitions(org_id: str, hours: int = 24) -> str:
    """Find recent monitor state transitions for a customer org from alerting logs."""
    now = datetime.now(timezone.utc)
    from_ts = now - timedelta(hours=hours)

    # The message embeds org_id= as plain text, not as an extracted attribute
    query = f'service:alerting* "org_id={org_id}" "Processed transition"'

    print(f"[searching alerting logs for org {org_id} over last {hours}h...]", file=sys.stderr)
    logs = _search_logs(query, from_ts, now, limit=300)

    # Collect transitions per monitor — most recent per monitor_id
    monitors: OrderedDict[str, dict] = OrderedDict()
    for log in reversed(logs):
        msg = log.get("message", "")
        m = _TRANSITION_RE.search(msg)
        if m and m.group(1) == org_id:
            mid = m.group(2)
            monitors[mid] = {
                "monitor_id": mid,
                "result_id": m.group(3),
                "transition_type": m.group(4),
                "timestamp": log.get("timestamp"),
            }

    if not monitors:
        return f"No monitor transitions found for org {org_id} in the last {hours}h."

    lines = [
        f"Monitor transitions for org {org_id} (last {hours}h, {len(monitors)} monitors)",
        "",
    ]
    for m in monitors.values():
        ts = m["timestamp"]
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(ts, "strftime") else str(ts)
        lines.append(
            f"[{ts_str}]  monitor {m['monitor_id']}  {m['transition_type']}"
            f"  ← use with 'monitor state {org_id} {m['monitor_id']}'"
        )
    lines.append("")
    lines.append(f"Run 'dd-admin monitor state {org_id} <monitor_id>' to investigate.")

    return "\n".join(lines).rstrip()
