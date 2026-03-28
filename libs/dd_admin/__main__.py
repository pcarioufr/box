#!/usr/bin/env python3
"""dd-admin CLI — Datadog internal admin tooling.

Subcommands:
  monitor   Debug monitor evaluation via Monitor Admin APIs (VPN-required)
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


def add_cluster_arg(parser):
    """Add --cluster override to a parser."""
    parser.add_argument(
        "--cluster",
        help="Override auto-derived cluster (default: derived from org_id)",
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

    # ── Parse ────────────────────────────────────────────────────────
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "monitor" and not hasattr(args, "func"):
        monitor_parser.print_help()
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
