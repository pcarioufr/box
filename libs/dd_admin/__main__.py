#!/usr/bin/env python3
"""dd-admin CLI — Datadog internal admin tooling.

Subcommands:
  monitor   Debug monitor evaluation via Monitor Admin APIs (VPN-required)
  watchdog  Debug Watchdog alert lifecycle via Data Science Admin APIs (VPN-required)
"""

import argparse
import sys
import logging

from libs.dd_admin.monitor_admin import (
    cluster_from_org_id,
    get_state,
    get_results,
    get_result_detail,
    get_group_payload,
    reevaluate,
    downtime_search,
)
from libs.dd_admin.watchdog_admin import (
    dc_from_cluster,
    dc_from_org_id,
    get_bundle,
    get_signals,
)
from libs.dd_admin.log_search import (
    find_watchdog_bundles,
    find_monitor_transitions,
    get_bundle_history,
)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)


def resolve_cluster(args) -> str:
    """Resolve cluster from explicit flag or org_id."""
    if args.cluster:
        return args.cluster
    cluster = cluster_from_org_id(args.org_id)
    print(f"[auto-derived cluster: {cluster}]", file=sys.stderr)
    return cluster


def resolve_dc(args) -> str:
    """Resolve watchdog dc from explicit flag, dc, or org_id."""
    if args.dc:
        return args.dc
    cluster = args.cluster if args.cluster else cluster_from_org_id(args.org_id)
    dc = dc_from_cluster(cluster)
    print(f"[auto-derived dc: {dc}]", file=sys.stderr)
    return dc


def cmd_state(args):
    cluster = resolve_cluster(args)
    print(get_state(cluster, args.org_id, args.monitor_id))


def cmd_results(args):
    cluster = resolve_cluster(args)
    print(get_results(cluster, args.org_id, args.monitor_id, args.from_ts, args.to_ts))


def cmd_detail(args):
    cluster = resolve_cluster(args)
    status_filter = args.status.split(",") if args.status else None
    print(get_result_detail(
        cluster, args.org_id, args.result_id, args.timestamp,
        group_filter=args.group, status_filter=status_filter,
    ))


def cmd_payload(args):
    cluster = resolve_cluster(args)
    print(get_group_payload(cluster, args.org_id, args.monitor_id, group_filter=args.group))


def cmd_reevaluate(args):
    cluster = resolve_cluster(args)
    print(reevaluate(cluster, args.org_id, args.result_id, args.timestamp, group_filter=args.group))


def cmd_downtimes(args):
    cluster = resolve_cluster(args)
    print(downtime_search(cluster, args.org_id, args.query, size=args.size))


def cmd_watchdog_bundle(args):
    dc = resolve_dc(args)
    print(get_bundle(dc, args.org_id, args.bundle_id, shadow_name=args.shadow_name))


def cmd_watchdog_signals(args):
    dc = resolve_dc(args)
    print(get_signals(dc, args.org_id, args.signal_key, shadow_name=args.shadow_name))


def cmd_watchdog_find(args):
    print(find_watchdog_bundles(args.org_id, hours=args.hours, status_filter=args.status))


def cmd_watchdog_history(args):
    print(get_bundle_history(args.org_id, args.bundle_id, hours=args.hours))


def cmd_monitor_find(args):
    print(find_monitor_transitions(args.org_id, hours=args.hours))


def add_cluster_arg(parser):
    """Add --cluster override to a parser."""
    parser.add_argument(
        "--cluster",
        help="Override auto-derived cluster (default: derived from org_id)",
    )


def add_dc_args(parser):
    """Add --dc and --cluster override to a watchdog parser."""
    parser.add_argument(
        "--dc",
        help="Override datacenter domain (e.g. us1.prod.dog). Takes precedence over --cluster.",
    )
    parser.add_argument(
        "--cluster",
        help="Override auto-derived cluster (default: derived from org_id)",
    )
    parser.add_argument(
        "--shadow-name",
        dest="shadow_name",
        help="Shadow pipeline name (optional, for shadow bundle reads)",
    )


def main():
    parser = argparse.ArgumentParser(
        prog="dd-admin",
        description="Datadog internal admin tooling",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── monitor ──────────────────────────────────────────────────────
    monitor_parser = subparsers.add_parser(
        "monitor", help="Debug monitor evaluation (VPN required)",
    )
    monitor_sub = monitor_parser.add_subparsers(dest="monitor_command", help="Monitor subcommands")

    # state
    p = monitor_sub.add_parser("state", help="Get current monitor state and group statuses")
    p.add_argument("org_id", help="Organization ID")
    p.add_argument("monitor_id", help="Monitor ID")
    add_cluster_arg(p)
    p.set_defaults(func=cmd_state)

    # results
    p = monitor_sub.add_parser("results", help="List evaluations in a time range")
    p.add_argument("org_id", help="Organization ID")
    p.add_argument("monitor_id", help="Monitor ID")
    p.add_argument("--from", dest="from_ts", required=True, help="Start time (ISO 8601 UTC)")
    p.add_argument("--to", dest="to_ts", required=True, help="End time (ISO 8601 UTC)")
    add_cluster_arg(p)
    p.set_defaults(func=cmd_results)

    # detail
    p = monitor_sub.add_parser("detail", help="Per-group values, thresholds, and margins for one evaluation")
    p.add_argument("org_id", help="Organization ID")
    p.add_argument("result_id", help="Result ID (from 'results' command)")
    p.add_argument("--timestamp", required=True, help="Evaluation timestamp (ISO 8601 UTC)")
    p.add_argument("--group", help="Filter groups by name substring")
    p.add_argument("--status", help="Filter by status (comma-separated: OK,ALERT,WARNING,NO_DATA,SKIPPED,OK_STAY_ALERT)")
    add_cluster_arg(p)
    p.set_defaults(func=cmd_detail)

    # payload
    p = monitor_sub.add_parser("payload", help="Alert history (triggered/resolved/notified timestamps)")
    p.add_argument("org_id", help="Organization ID")
    p.add_argument("monitor_id", help="Monitor ID")
    p.add_argument("--group", help="Filter groups by name substring")
    add_cluster_arg(p)
    p.set_defaults(func=cmd_payload)

    # reevaluate
    p = monitor_sub.add_parser("reevaluate", help="Re-evaluate a past result with current data (late-data diagnosis)")
    p.add_argument("org_id", help="Organization ID")
    p.add_argument("result_id", help="Result ID (from 'results' command)")
    p.add_argument("--timestamp", required=True, help="Evaluation timestamp (ISO 8601 UTC)")
    p.add_argument("--group", help="Filter groups by name substring")
    add_cluster_arg(p)
    p.set_defaults(func=cmd_reevaluate)

    # downtimes
    p = monitor_sub.add_parser("downtimes", help="Search downtimes that may have silenced a monitor")
    p.add_argument("org_id", help="Organization ID")
    p.add_argument("query", help="Search query for downtimes")
    p.add_argument("--size", type=int, default=50, help="Number of results (default: 50)")
    add_cluster_arg(p)
    p.set_defaults(func=cmd_downtimes)

    # find (log-based discovery)
    p = monitor_sub.add_parser("find", help="Find monitors with recent transitions for an org (via org 2 logs, needs DD_API_KEY/DD_APP_KEY)")
    p.add_argument("org_id", help="Customer organization ID to search for")
    p.add_argument("--hours", type=int, default=24, help="Look-back window in hours (default: 24)")
    p.set_defaults(func=cmd_monitor_find)

    # ── watchdog ─────────────────────────────────────────────────────
    watchdog_parser = subparsers.add_parser(
        "watchdog", help="Debug Watchdog alert lifecycle (VPN required)",
    )
    watchdog_sub = watchdog_parser.add_subparsers(dest="watchdog_command", help="Watchdog subcommands")

    # bundle
    p = watchdog_sub.add_parser("bundle", help="Get bundle info: scope, status, signal key")
    p.add_argument("org_id", help="Organization ID")
    p.add_argument("bundle_id", help="Bundle UUID (from watchdog-alert-lifecycle URL)")
    add_dc_args(p)
    p.set_defaults(func=cmd_watchdog_bundle)

    # signals
    p = watchdog_sub.add_parser("signals", help="Get signal history: anomaly timeline, values vs baseline")
    p.add_argument("org_id", help="Organization ID")
    p.add_argument("signal_key", help="Signal key (from 'bundle' output or watchdog-alert-lifecycle URL)")
    add_dc_args(p)
    p.set_defaults(func=cmd_watchdog_signals)

    # find (log-based discovery)
    p = watchdog_sub.add_parser("find", help="Find Watchdog bundles for an org from org 2 logs (needs DD_API_KEY/DD_APP_KEY)")
    p.add_argument("org_id", help="Customer organization ID to search for")
    p.add_argument("--hours", type=int, default=24, help="Look-back window in hours (default: 24)")
    p.add_argument("--status", choices=["ONGOING", "RESOLVED"], help="Filter by bundle status")
    p.set_defaults(func=cmd_watchdog_find)

    # history (log-based bundle timeline)
    p = watchdog_sub.add_parser("history", help="Full lifecycle timeline for a bundle from org 2 logs (needs DD_API_KEY/DD_APP_KEY)")
    p.add_argument("org_id", help="Customer organization ID")
    p.add_argument("bundle_id", help="Bundle UUID to reconstruct history for")
    p.add_argument("--hours", type=int, default=48, help="Look-back window in hours (default: 48)")
    p.set_defaults(func=cmd_watchdog_history)

    # ── Parse ────────────────────────────────────────────────────────
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "monitor" and not hasattr(args, "func"):
        monitor_parser.print_help()
        sys.exit(1)

    if args.command == "watchdog" and not hasattr(args, "func"):
        watchdog_parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
