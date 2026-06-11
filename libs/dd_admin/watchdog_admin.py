"""Watchdog Admin API client.

Wraps Datadog's internal Watchdog alert lifecycle APIs (VPN-gated, no auth).
Backend: apps/internal_data_science_ui in dogweb (datascience.{dc}/api/v1/).
"""

import json
from datetime import datetime, timezone

import requests

from libs.dd_admin.monitor_admin import _load_config, cluster_from_org_id


# ── Cluster → DC domain (read from config) ───────────────────────────

def _watchdog_clusters() -> dict:
    return _load_config()["watchdog_admin"]["clusters"]


def dc_from_cluster(cluster: str) -> str:
    clusters = _watchdog_clusters()
    dc = clusters.get(cluster)
    if not dc:
        raise ValueError(f"Unknown cluster: {cluster}. Valid: {', '.join(clusters)}")
    return dc


def dc_from_org_id(org_id: str) -> str:
    return dc_from_cluster(cluster_from_org_id(org_id))


# ── API ──────────────────────────────────────────────────────────────

def api_get(dc: str, path: str, params: dict) -> dict | list:
    """GET from a Watchdog Admin API endpoint."""
    url = f"https://datascience.{dc}/api/v1{path}"
    resp = requests.get(
        url,
        params={k: v for k, v in params.items() if v is not None},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _ts(epoch: int | None) -> str:
    if epoch is None:
        return "N/A"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


# ── Commands ─────────────────────────────────────────────────────────

def get_bundle(dc: str, org_id: str, bundle_id: str, shadow_name: str | None = None) -> str:
    """Get bundle info — aggregates, scope, status, signal keys."""
    data = api_get(dc, "/alert_lifecycle/get_bundle_info", {
        "input_org_id": org_id,
        "input_bundle_id": bundle_id,
        "input_shadow_name": shadow_name,
    })

    if not data:
        return f"No bundle found for bundle_id={bundle_id} org={org_id}"

    lines = [
        f"Bundle {bundle_id} (org {org_id}) on {dc}",
        f"Aggregates: {len(data)}",
        "",
    ]

    for i, agg in enumerate(data):
        source_raw = agg.get("source", "{}")
        try:
            source = json.loads(source_raw)
        except (json.JSONDecodeError, TypeError):
            source = {}

        scope = source.get("scope") or {}
        parent_signal_key = source.get("parent_signal_key")
        model_id = source.get("model_id")

        lines += [
            f"Aggregate {i + 1}: {agg.get('aggregate_id')}",
            f"  Type:    {agg.get('type')}",
            f"  Status:  {agg.get('status_name')}",
            f"  Window:  {_ts(agg.get('start_epoch'))} → {_ts(agg.get('end_epoch') or agg.get('last_signal_added_at'))}",
            f"  Created: {_ts(agg.get('created_at'))}  Updated: {_ts(agg.get('updated_at'))}",
            f"  Last signal added: {_ts(agg.get('last_signal_added_at'))}",
        ]

        if scope:
            lines.append("  Scope:")
            for k, v in scope.items():
                lines.append(f"    {k}: {v}")

        if model_id:
            lines.append(f"  Model: {model_id}")

        if parent_signal_key:
            lines.append(f"  Signal key: {parent_signal_key}  ← use with 'watchdog signals'")

        lines.append("")

    return "\n".join(lines).rstrip()


def get_signals(dc: str, org_id: str, signal_key: str, shadow_name: str | None = None) -> str:
    """Get signal history — anomaly timeline with values vs baseline."""
    data = api_get(dc, "/alert_lifecycle/signal_history", {
        "org_id": org_id,
        "signal_key": signal_key,
        "shadow_name": shadow_name,
    })

    if not data:
        return f"No signal history found for signal_key={signal_key} org={org_id}"

    # data is a dict: {timestamp_str: signal_object}
    entries = sorted(data.items(), key=lambda x: int(x[0]))

    lines = [
        f"Signal {signal_key} (org {org_id}) on {dc}",
        f"History entries: {len(entries)}",
        "",
    ]

    for ts_str, sig in entries:
        ts = _ts(int(ts_str))
        state = sig.get("state") or {}
        stats = sig.get("stats") or {}
        row_stats = stats.get("resource_row_level_stats") or {}
        apm = sig.get("apm_metadata") or {}

        status = state.get("status", "?")
        direction = state.get("direction", "?")
        start = _ts(state.get("start"))
        end = _ts(state.get("end")) if state.get("end") else "ongoing"

        line = (
            f"[{ts}]  {status} {direction}"
            f" | window: {start} → {end}"
            f" | model: {sig.get('model_id', '?')}"
        )

        anomalous_val = row_stats.get("anomalous_value")
        baseline_val = row_stats.get("baseline_value")
        if anomalous_val is not None and baseline_val is not None and baseline_val != 0:
            ratio = anomalous_val / baseline_val
            line += f" | {anomalous_val:.4f} vs baseline {baseline_val:.4f} (×{ratio:.1f})"
        elif anomalous_val is not None:
            line += f" | anomalous: {anomalous_val:.4f}"

        if apm.get("service"):
            line += f" | {apm['service']}"

        lines.append(line)

    # Show queries from the last entry for reference
    if entries:
        last_sig = entries[-1][1]
        queries = last_sig.get("queries") or {}
        if queries.get("metric_query"):
            lines += ["", f"Metric query: {queries['metric_query']}"]
        if queries.get("anomalies_metric_query"):
            lines.append(f"Anomaly query: {queries['anomalies_metric_query']}")

    return "\n".join(lines)
