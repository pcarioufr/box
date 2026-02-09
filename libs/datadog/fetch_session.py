#!/usr/bin/env python3
"""Fetch a RUM session and build a chronological timeline YAML."""

import os
import time
import yaml
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.rum_api import RUMApi
from datadog_api_client.v2.model.rum_search_events_request import RUMSearchEventsRequest
from datadog_api_client.v2.model.rum_query_filter import RUMQueryFilter
from datadog_api_client.v2.model.rum_query_page_options import RUMQueryPageOptions
from datadog_api_client.v2.model.rum_sort import RUMSort

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DEFAULT_SUBDIR = "datadog"


# ---------------------------------------------------------------------------
# YAML formatting
# ---------------------------------------------------------------------------

class _Dumper(yaml.SafeDumper):
    pass


def _str_representer(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


def _list_representer(dumper, data):
    if not data:
        return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=False)


_Dumper.add_representer(str, _str_representer)
_Dumper.add_representer(list, _list_representer)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_host(url: str) -> str:
    """Strip the Datadog host from a URL, keeping path + query."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query
    return path


def _get_nested(d, *keys, default=None):
    """Safely traverse nested dicts."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d


def _get_attrs(event: dict) -> dict:
    """Return the inner RUM attributes dict from an API event."""
    return _get_nested(event, "attributes", "attributes", default={})


def _get_timestamp_ms(event: dict) -> int:
    """Extract event timestamp as milliseconds since epoch."""
    ts = _get_nested(event, "attributes", "timestamp")
    if isinstance(ts, datetime):
        return int(ts.timestamp() * 1000)
    if isinstance(ts, str):
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return int(dt.timestamp() * 1000)
    if isinstance(ts, (int, float)):
        return int(ts) if ts > 1e12 else int(ts * 1000)
    return 0


def _format_offset(ms: int, start_ms: int) -> str:
    """Format a timestamp as seconds since session start, e.g. '12.3s'."""
    seconds = (ms - start_ms) / 1000
    if seconds == int(seconds):
        return f"{int(seconds)}.0s"
    return f"{seconds:.1f}s"


def _resolve_attribute(attrs: dict, facet_path: str):
    """Resolve a Datadog facet path like '@feature_flags.acme' from a nested attrs dict.

    Strips leading '@' and traverses dot-separated keys.
    Returns None if not found.
    """
    path = facet_path.lstrip("@")
    keys = path.split(".")
    val = attrs
    for key in keys:
        if isinstance(val, dict):
            val = val.get(key)
        else:
            return None
        if val is None:
            return None
    return val


def _apply_app_filter(query: str) -> str:
    """Append @application.id filter from DD_RUM_APP_ID if set and not already in query."""
    app_id = os.getenv("DD_RUM_APP_ID")
    if app_id and "@application.id:" not in query:
        query = f"{query} @application.id:{app_id}"
    return query


def _get_api_config() -> Configuration:
    api_key = os.getenv("DD_API_KEY")
    app_key = os.getenv("DD_APP_KEY")
    dd_site = os.getenv("DD_SITE", "datadoghq.com")
    if not api_key or not app_key:
        raise ValueError(
            "Missing Datadog credentials. Set DD_API_KEY and DD_APP_KEY environment variables."
        )
    configuration = Configuration()
    configuration.api_key["apiKeyAuth"] = api_key
    configuration.api_key["appKeyAuth"] = app_key
    configuration.server_variables["site"] = dd_site
    return configuration


# ---------------------------------------------------------------------------
# API fetching (paginated)
# ---------------------------------------------------------------------------

def _fetch_all_events(api_instance: RUMApi, query: str) -> List[dict]:
    """Fetch all RUM events matching *query*, handling cursor pagination."""
    query = _apply_app_filter(query)
    now = datetime.now(timezone.utc)
    from_time = (now - timedelta(days=90)).isoformat()
    to_time = now.isoformat()

    all_events: List[dict] = []
    cursor = None

    while True:
        page_opts = RUMQueryPageOptions(limit=1000)
        if cursor:
            page_opts = RUMQueryPageOptions(limit=1000, cursor=cursor)

        body = RUMSearchEventsRequest(
            filter=RUMQueryFilter(
                query=query,
                _from=from_time,
                to=to_time,
            ),
            page=page_opts,
            sort=RUMSort.TIMESTAMP_ASCENDING,
        )

        for attempt in range(3):
            try:
                response = api_instance.search_rum_events(body=body)
                break
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"  API error, retrying in {wait}s: {e}")
                    time.sleep(wait)
                else:
                    raise
        events = response.data if hasattr(response, 'data') else []

        for event in events:
            all_events.append(event.to_dict() if hasattr(event, 'to_dict') else event)

        # Next page?
        next_cursor = _get_nested(response.to_dict() if hasattr(response, 'to_dict') else {},
                                  "meta", "page", "after")
        if next_cursor:
            cursor = next_cursor
        else:
            break

    return all_events


# ---------------------------------------------------------------------------
# Timeline construction
# ---------------------------------------------------------------------------

def _build_timeline(
    view_events: List[dict],
    action_events: List[dict],
    view_attributes: Optional[List[str]] = None,
) -> dict:
    """Build the chronological session timeline from view + action events.

    Returns {"timeline": [...], "session_start_ms": int}.
    """
    # 1. View lookup: view_id -> metadata
    view_info: Dict[str, dict] = {}
    for event in view_events:
        attrs = _get_attrs(event)
        view_id = _get_nested(attrs, "view", "id")
        if not view_id:
            continue
        info = {
            "name": _get_nested(attrs, "view", "name"),
            "url": _get_nested(attrs, "view", "url"),
            "referrer": _get_nested(attrs, "view", "referrer"),
            "timestamp_ms": _get_timestamp_ms(event),
        }
        # Resolve extra view-level attributes
        if view_attributes:
            extras = {}
            for facet in view_attributes:
                val = _resolve_attribute(attrs, facet)
                if val is not None:
                    extras[facet.lstrip("@")] = val
            info["_extras"] = extras
        view_info[view_id] = info

    # 2. Unified event stream: (timestamp_ms, view_id, kind, data)
    stream = []
    for event in view_events:
        attrs = _get_attrs(event)
        view_id = _get_nested(attrs, "view", "id")
        if view_id:
            stream.append((_get_timestamp_ms(event), view_id, "marker", None))

    for event in action_events:
        attrs = _get_attrs(event)
        view_id = _get_nested(attrs, "view", "id")
        if not view_id:
            continue
        frustration_type = _get_nested(attrs, "action", "frustration", "type")
        stream.append((_get_timestamp_ms(event), view_id, "action", {
            "type": _get_nested(attrs, "action", "type", default="unknown"),
            "name": _get_nested(attrs, "action", "name") or _get_nested(attrs, "action", "target", "name") or "unknown",
            "frustration": bool(frustration_type) if frustration_type else False,
            "timestamp_ms": _get_timestamp_ms(event),
        }))

    stream.sort(key=lambda x: x[0])

    if not stream:
        return {"timeline": [], "session_start_ms": 0}

    session_start_ms = stream[0][0]

    # 3. Walk stream, group consecutive same-view_id entries into stints
    stints: List[dict] = []
    current = None

    for ts, view_id, kind, data in stream:
        if current is None or current["view_id"] != view_id:
            current = {"view_id": view_id, "start_ms": ts, "actions": []}
            stints.append(current)
        if kind == "action":
            current["actions"].append(data)

    # 4. Build timeline entries
    timeline = []
    seen: set = set()

    for stint in stints:
        vid = stint["view_id"]
        info = view_info.get(vid, {})

        url = info.get("url")
        view_label = _strip_host(url) if url else info.get("name", "unknown")
        entry: Dict[str, Any] = {"view": view_label, "view_id": vid}

        if vid not in seen:
            entry["visit"] = "new"
            referrer = info.get("referrer")
            if referrer:
                entry["referrer"] = _strip_host(referrer)
            seen.add(vid)
        else:
            entry["visit"] = "return"

        entry["at"] = _format_offset(stint["start_ms"], session_start_ms)

        # Extra view-level attributes
        if view_attributes:
            extras = info.get("_extras", {})
            for key, val in extras.items():
                entry[key] = val

        actions = []
        for a in stint["actions"]:
            ae: Dict[str, Any] = {"type": a["type"], "name": a["name"]}
            if a["frustration"]:
                ae["frustration"] = True
            ae["at"] = _format_offset(a["timestamp_ms"], session_start_ms)
            actions.append(ae)
        entry["actions"] = actions

        timeline.append(entry)

    return {"timeline": timeline, "session_start_ms": session_start_ms}


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------

def _extract_session_metadata(
    view_events: List[dict],
    session_id: str,
    session_start_ms: int,
    session_end_ms: int,
    session_attributes: Optional[List[str]] = None,
) -> dict:
    """Build the session: block from the first view event."""
    started_at = datetime.fromtimestamp(session_start_ms / 1000, tz=timezone.utc)

    meta: Dict[str, Any] = {
        "id": session_id,
        "started_at": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if not view_events:
        return meta

    attrs = _get_attrs(view_events[0])

    # User
    usr = _get_nested(attrs, "usr", default={})
    if isinstance(usr, dict):
        user_block: Dict[str, Any] = {}
        email = usr.get("email")
        if email:
            user_block["email"] = str(email)
        org_id = usr.get("org_id")
        if org_id is not None:
            try:
                user_block["org_id"] = int(float(str(org_id)))
            except (ValueError, TypeError):
                user_block["org_id"] = str(org_id)
        org_name = usr.get("org_name")
        if org_name:
            user_block["org_name"] = str(org_name)
        if user_block:
            meta["user"] = user_block

    # Country
    country = _get_nested(attrs, "geo", "country")
    if country:
        meta["country"] = country

    # Duration
    duration_ms = session_end_ms - session_start_ms
    if duration_ms > 0:
        meta["duration_s"] = round(duration_ms / 1000, 1)

    # Extra session-level attributes
    if session_attributes:
        for facet in session_attributes:
            val = _resolve_attribute(attrs, facet)
            if val is not None:
                key = facet.lstrip("@")
                meta[key] = val

    return meta


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _fetch_and_build_session(
    api: RUMApi,
    session_id: str,
    session_attributes: Optional[List[str]] = None,
    view_attributes: Optional[List[str]] = None,
) -> Optional[dict]:
    """Fetch events for a single session and return the output data dict, or None."""
    view_events = _fetch_all_events(api, f"@type:view @session.id:{session_id}")
    action_events = _fetch_all_events(api, f"@type:action @action.type:click @session.id:{session_id}")

    logger.info(f"  {len(view_events)} views, {len(action_events)} actions")

    if not view_events and not action_events:
        return None

    result = _build_timeline(view_events, action_events, view_attributes=view_attributes)
    timeline = result["timeline"]
    session_start_ms = result["session_start_ms"]

    all_ts = [_get_timestamp_ms(e) for e in view_events + action_events]
    session_end_ms = max(all_ts) if all_ts else session_start_ms

    session_meta = _extract_session_metadata(
        view_events, session_id, session_start_ms, session_end_ms,
        session_attributes=session_attributes,
    )

    return {"session": session_meta, "timeline": timeline}


def _write_session_yaml(data: dict, output_path: Path) -> None:
    """Write a session data dict to a YAML file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        yaml.dump(data, f, Dumper=_Dumper, default_flow_style=False,
                  sort_keys=False, allow_unicode=True)


def fetch_session(
    session_id: str,
    output_file: Optional[str] = None,
    working_folder: Optional[str] = None,
    session_attributes: Optional[List[str]] = None,
    view_attributes: Optional[List[str]] = None,
) -> None:
    """Fetch all events for a RUM session and write a timeline YAML."""
    configuration = _get_api_config()

    with ApiClient(configuration) as api_client:
        api = RUMApi(api_client)
        logger.info(f"Fetching session {session_id}...")
        data = _fetch_and_build_session(
            api, session_id,
            session_attributes=session_attributes,
            view_attributes=view_attributes,
        )

    if not data:
        logger.warning(f"No events found for session {session_id}")
        return

    if not output_file:
        output_file = f"session_{session_id[:8]}.yaml"

    if working_folder:
        output_path = DATA_DIR / working_folder / DEFAULT_SUBDIR / output_file
    else:
        output_path = DATA_DIR / DEFAULT_SUBDIR / output_file

    _write_session_yaml(data, output_path)
    logger.info(f"Session timeline saved to: {output_path}")
    logger.info(f"  Timeline entries: {len(data['timeline'])}")


def _discover_by_search(api: RUMApi, query: str, from_iso: str, to_iso: str, limit: int) -> List[str]:
    """Discover session IDs by paginating a search query."""
    # Ensure @type:view so we get one event per session
    if "@type:" not in query:
        query = f"@type:view {query}"
    query = _apply_app_filter(query)

    logger.info(f"Discovering sessions (search)...")
    logger.info(f"  Query: {query}")

    seen_ids: set = set()
    session_ids: list = []
    cursor = None

    while len(session_ids) < limit:
        page_opts = RUMQueryPageOptions(limit=1000)
        if cursor:
            page_opts = RUMQueryPageOptions(limit=1000, cursor=cursor)

        body = RUMSearchEventsRequest(
            filter=RUMQueryFilter(query=query, _from=from_iso, to=to_iso),
            page=page_opts,
            sort=RUMSort.TIMESTAMP_ASCENDING,
        )

        response = api.search_rum_events(body=body)
        events = response.data if hasattr(response, 'data') else []
        if not events:
            break

        for event in events:
            e = event.to_dict() if hasattr(event, 'to_dict') else event
            sid = _get_nested(_get_attrs(e), "session", "id")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                session_ids.append(sid)
                if len(session_ids) >= limit:
                    break

        if len(session_ids) >= limit:
            break

        resp_dict = response.to_dict() if hasattr(response, 'to_dict') else {}
        next_cursor = _get_nested(resp_dict, "meta", "page", "after")
        if next_cursor:
            cursor = next_cursor
        else:
            break

    return session_ids


def _discover_by_aggregate(api: RUMApi, query: str, from_iso: str, to_iso: str, limit: int) -> List[str]:
    """Discover session IDs via aggregate group-by @session.id, sorted by view count desc."""
    from datadog_api_client.v2.model.rum_aggregate_request import RUMAggregateRequest
    from datadog_api_client.v2.model.rum_compute import RUMCompute
    from datadog_api_client.v2.model.rum_compute_type import RUMComputeType
    from datadog_api_client.v2.model.rum_group_by import RUMGroupBy
    from datadog_api_client.v2.model.rum_aggregation_function import RUMAggregationFunction
    from datadog_api_client.v2.model.rum_aggregate_sort import RUMAggregateSort
    from datadog_api_client.v2.model.rum_aggregate_sort_type import RUMAggregateSortType
    from datadog_api_client.v2.model.rum_sort_order import RUMSortOrder

    # Ensure @type:view for the view query
    if "@type:" not in query:
        query = f"@type:view {query}"
    query = _apply_app_filter(query)

    logger.info(f"Discovering sessions (aggregate)...")
    logger.info(f"  Query: {query}")

    body = RUMAggregateRequest(
        filter=RUMQueryFilter(query=query, _from=from_iso, to=to_iso),
        compute=[
            RUMCompute(
                aggregation=RUMAggregationFunction.COUNT,
                metric="*",
                type=RUMComputeType.TOTAL,
            )
        ],
        group_by=[
            RUMGroupBy(
                facet="@session.id",
                limit=limit,
                sort=RUMAggregateSort(
                    aggregation=RUMAggregationFunction.COUNT,
                    metric="*",
                    order=RUMSortOrder.DESCENDING,
                    type=RUMAggregateSortType.MEASURE,
                ),
            )
        ],
    )

    response = api.aggregate_rum_events(body=body)
    buckets = response.data.buckets if hasattr(response.data, 'buckets') else []

    session_ids = []
    for bucket in buckets:
        b = bucket.to_dict() if hasattr(bucket, 'to_dict') else bucket
        by = b.get("by", {})
        sid = by.get("@session.id")
        if sid:
            session_ids.append(sid)

    return session_ids


def fetch_sessions(
    query: str,
    from_time: str,
    to_time: Optional[str] = None,
    limit: int = 100,
    output_dir: Optional[str] = None,
    working_folder: Optional[str] = None,
    views: bool = False,
    session_attributes: Optional[List[str]] = None,
    view_attributes: Optional[List[str]] = None,
) -> None:
    """Fetch multiple sessions matching a RUM query and write each as a YAML file.

    When views=True, the query is treated as a view query and session IDs are
    discovered via aggregate (group by @session.id, sorted by matching view count).
    """
    import json
    from libs.datadog.query_rum import parse_time

    configuration = _get_api_config()

    from_ms = parse_time(from_time)
    to_ms = parse_time(to_time) if to_time else int(datetime.now(timezone.utc).timestamp() * 1000)
    from_iso = datetime.fromtimestamp(from_ms / 1000, tz=timezone.utc).isoformat()
    to_iso = datetime.fromtimestamp(to_ms / 1000, tz=timezone.utc).isoformat()

    logger.info(f"  From: {from_iso}")
    logger.info(f"  To: {to_iso}")

    with ApiClient(configuration) as api_client:
        api = RUMApi(api_client)

        if views:
            session_ids = _discover_by_aggregate(api, query, from_iso, to_iso, limit)
        else:
            session_ids = _discover_by_search(api, query, from_iso, to_iso, limit)

        logger.info(f"  Found {len(session_ids)} unique sessions")

        if not session_ids:
            logger.warning("No sessions found matching query")
            return

        # Determine output directory
        if not output_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"sessions_{timestamp}"

        if working_folder:
            out_path = DATA_DIR / working_folder / DEFAULT_SUBDIR / output_dir
        else:
            out_path = DATA_DIR / DEFAULT_SUBDIR / output_dir

        out_path.mkdir(parents=True, exist_ok=True)

        # Write query.json for tracking
        query_meta = {
            "query": query,
            "mode": "views" if views else "sessions",
            "from": from_iso,
            "to": to_iso,
            "limit": limit,
            "session_count": len(session_ids),
            "session_ids": session_ids,
        }
        with open(out_path / "query.json", 'w') as f:
            json.dump(query_meta, f, indent=2, default=str)

        # Fetch each session (skip already-fetched for resumability)
        fetched = 0
        skipped = 0
        for i, sid in enumerate(session_ids, 1):
            yaml_path = out_path / f"{sid[:8]}.yaml"
            if yaml_path.exists():
                skipped += 1
                continue
            logger.info(f"[{i}/{len(session_ids)}] Fetching session {sid[:8]}...")
            data = _fetch_and_build_session(
                api, sid,
                session_attributes=session_attributes,
                view_attributes=view_attributes,
            )
            if data:
                _write_session_yaml(data, yaml_path)
                fetched += 1
            else:
                logger.warning(f"  No events found, skipping")

    if skipped:
        logger.info(f"Done. {fetched} fetched, {skipped} already existed in: {out_path}")
    else:
        logger.info(f"Done. {fetched} sessions saved to: {out_path}")


def fetch_view(
    view_id: str,
    output_file: Optional[str] = None,
    working_folder: Optional[str] = None,
) -> None:
    """Fetch a single RUM view event and dump its attributes as YAML."""
    configuration = _get_api_config()

    with ApiClient(configuration) as api_client:
        api = RUMApi(api_client)

        logger.info(f"Fetching view {view_id}...")
        events = _fetch_all_events(api, f"@type:view @view.id:{view_id}")

        if not events:
            logger.warning(f"No view found for view_id {view_id}")
            return

        logger.info(f"  Found {len(events)} event(s)")

    # Extract the inner attributes (the useful RUM data)
    attrs = _get_attrs(events[0])

    # Write
    if not output_file:
        output_file = f"view_{view_id[:8]}.yaml"

    if working_folder:
        output_path = DATA_DIR / working_folder / DEFAULT_SUBDIR / output_file
    else:
        output_path = DATA_DIR / DEFAULT_SUBDIR / output_file

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        yaml.dump(attrs, f, Dumper=_Dumper, default_flow_style=False,
                  sort_keys=False, allow_unicode=True)

    logger.info(f"View saved to: {output_path}")
