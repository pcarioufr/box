#!/usr/bin/env python3
"""RUM aggregate functionality using Datadog API for top N and time series queries."""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.rum_api import RUMApi
from datadog_api_client.v2.model.rum_aggregate_request import RUMAggregateRequest
from datadog_api_client.v2.model.rum_query_filter import RUMQueryFilter
from datadog_api_client.v2.model.rum_group_by import RUMGroupBy
from datadog_api_client.v2.model.rum_group_by_histogram import RUMGroupByHistogram
from datadog_api_client.v2.model.rum_aggregate_sort import RUMAggregateSort
from datadog_api_client.v2.model.rum_aggregate_sort_type import RUMAggregateSortType
from datadog_api_client.v2.model.rum_sort_order import RUMSortOrder
from datadog_api_client.v2.model.rum_compute import RUMCompute
from datadog_api_client.v2.model.rum_compute_type import RUMComputeType
from datadog_api_client.v2.model.rum_aggregation_function import RUMAggregationFunction

logger = logging.getLogger(__name__)

# Base output directory for RUM data
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DEFAULT_SUBDIR = "datadog"  # Default subdirectory for auto-generated filenames


def parse_time(time_str: str) -> int:
    """Parse time string to Unix timestamp in milliseconds.

    Supports:
    - Relative times: "1h", "24h", "7d", "30d"
    - ISO format: "2025-01-01T00:00:00Z"
    - Unix timestamp: "1704067200"
    """
    # Try relative time
    if time_str.endswith('h'):
        hours = int(time_str[:-1])
        dt = datetime.utcnow() - timedelta(hours=hours)
        return int(dt.timestamp() * 1000)
    elif time_str.endswith('d'):
        days = int(time_str[:-1])
        dt = datetime.utcnow() - timedelta(days=days)
        return int(dt.timestamp() * 1000)

    # Try ISO format
    try:
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        return int(dt.timestamp() * 1000)
    except ValueError:
        pass

    # Try Unix timestamp
    try:
        timestamp = int(time_str)
        # If timestamp is in seconds (10 digits), convert to milliseconds
        if len(str(timestamp)) == 10:
            return timestamp * 1000
        return timestamp
    except ValueError:
        pass

    raise ValueError(f"Invalid time format: {time_str}")


def aggregate_rum_data(
    query: str,
    from_time: str,
    to_time: Optional[str] = None,
    group_by: Optional[List[str]] = None,
    compute_metric: str = "count",
    compute_aggregation: str = "count",
    timeseries_interval: Optional[str] = None,
    sort_order: str = "desc",
    limit: int = 10,
    output_file: Optional[str] = None,
    working_folder: Optional[str] = None
) -> None:
    """Aggregate RUM data from Datadog API.

    Args:
        query: RUM query string (Datadog query syntax)
        from_time: Start time (relative, ISO, or Unix timestamp)
        to_time: End time (default: now)
        group_by: List of facets to group by (e.g., ["@usr.org_id", "@geo.country"])
        compute_metric: Metric to compute (default: "*" for count, or field like "@view.time_spent")
        compute_aggregation: Aggregation function (count, sum, avg, min, max, percentile)
        timeseries_interval: Interval for time series (e.g., "1h", "1d") - enables time evolution
        sort_order: Sort order (desc for top N, asc for bottom N, none for lexicographic)
        limit: Maximum number of groups to return (default: 10)
        output_file: Output filename (e.g., "results.json")
        working_folder: Working folder name (e.g., "2026-02-03_analysis")
    """
    # Get credentials from environment
    api_key = os.getenv("DD_API_KEY")
    app_key = os.getenv("DD_APP_KEY")
    dd_site = os.getenv("DD_SITE", "datadoghq.com")

    if not api_key or not app_key:
        raise ValueError(
            "Missing Datadog credentials. Set DD_API_KEY and DD_APP_KEY environment variables.\n"
            "Create API and App keys at: https://app.datadoghq.com/organization-settings/api-keys"
        )

    # Parse timestamps
    from_timestamp = parse_time(from_time)
    to_timestamp = parse_time(to_time) if to_time else int(datetime.utcnow().timestamp() * 1000)

    query_type = "time series" if timeseries_interval else "top N"
    logger.info(f"Running RUM aggregate query ({query_type})...")
    logger.info(f"  Query: {query}")
    logger.info(f"  From: {datetime.fromtimestamp(from_timestamp/1000).isoformat()}Z")
    logger.info(f"  To: {datetime.fromtimestamp(to_timestamp/1000).isoformat()}Z")
    if group_by:
        logger.info(f"  Group by: {', '.join(group_by)}")
    logger.info(f"  Compute: {compute_aggregation}({compute_metric})")
    if timeseries_interval:
        logger.info(f"  Interval: {timeseries_interval}")
    logger.info(f"  Limit: {limit}")

    # Configure Datadog API client
    configuration = Configuration()
    configuration.api_key["apiKeyAuth"] = api_key
    configuration.api_key["appKeyAuth"] = app_key
    configuration.server_variables["site"] = dd_site

    # Build aggregate request
    with ApiClient(configuration) as api_client:
        api_instance = RUMApi(api_client)

        # Map aggregation function string to enum first (needed for sorting)
        agg_function_map = {
            "count": RUMAggregationFunction.COUNT,
            "cardinality": RUMAggregationFunction.CARDINALITY,
            "sum": RUMAggregationFunction.SUM,
            "avg": RUMAggregationFunction.AVG,
            "min": RUMAggregationFunction.MIN,
            "max": RUMAggregationFunction.MAX,
            "pc75": RUMAggregationFunction.PERCENTILE_75,
            "pc90": RUMAggregationFunction.PERCENTILE_90,
            "pc95": RUMAggregationFunction.PERCENTILE_95,
            "pc98": RUMAggregationFunction.PERCENTILE_98,
            "pc99": RUMAggregationFunction.PERCENTILE_99,
        }

        if compute_aggregation not in agg_function_map:
            raise ValueError(f"Invalid aggregation: {compute_aggregation}. Valid: {list(agg_function_map.keys())}")

        # Build group by clauses with sorting
        group_by_clauses = []
        if group_by:
            for facet in group_by:
                # Build RUMGroupBy with optional sorting
                group_by_params = {
                    "facet": facet,
                    "limit": limit,
                }

                # Add sort only if sort_order is specified (not "none")
                if sort_order != "none":
                    sort_order_enum = RUMSortOrder.DESCENDING if sort_order == "desc" else RUMSortOrder.ASCENDING
                    group_by_params["sort"] = RUMAggregateSort(
                        aggregation=agg_function_map[compute_aggregation],
                        metric=compute_metric if compute_metric != "count" else "*",
                        order=sort_order_enum,
                        type=RUMAggregateSortType.MEASURE,
                    )

                group_by_clauses.append(RUMGroupBy(**group_by_params))

        # Add timeseries group by if requested
        if timeseries_interval:
            # Convert interval to seconds
            interval_seconds = None
            if timeseries_interval.endswith('h'):
                interval_seconds = int(timeseries_interval[:-1]) * 3600
            elif timeseries_interval.endswith('d'):
                interval_seconds = int(timeseries_interval[:-1]) * 86400
            elif timeseries_interval.endswith('m'):
                interval_seconds = int(timeseries_interval[:-1]) * 60
            else:
                raise ValueError(f"Invalid interval format: {timeseries_interval}. Use format like '1h', '1d', '5m'")

            group_by_clauses.append(
                RUMGroupBy(
                    facet="@timestamp",
                    histogram=RUMGroupByHistogram(
                        interval=interval_seconds * 1000,  # Convert to milliseconds
                        min=from_timestamp,
                        max=to_timestamp,
                    ),
                )
            )

        # Build compute
        compute = RUMCompute(
            aggregation=agg_function_map[compute_aggregation],
            metric=compute_metric if compute_metric != "count" else "*",
            type=RUMComputeType.TOTAL,
        )

        # Build request
        body = RUMAggregateRequest(
            filter=RUMQueryFilter(
                query=query,
                _from=datetime.fromtimestamp(from_timestamp / 1000).isoformat() + "Z",
                to=datetime.fromtimestamp(to_timestamp / 1000).isoformat() + "Z",
            ),
            compute=[compute],
            group_by=group_by_clauses if group_by_clauses else None,
        )

        try:
            response = api_instance.aggregate_rum_events(body=body)
            buckets = response.data.buckets if hasattr(response.data, 'buckets') else []

            logger.info(f"✓ Retrieved {len(buckets)} aggregate buckets")

            # Prepare output path

            if not output_file:
                # Auto-generated filenames
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                query_type_slug = "timeseries" if timeseries_interval else "topn"
                output_file = f"rum_aggregate_{query_type_slug}_{timestamp}.json"

            # Construct full path
            if working_folder:
                # data/{working_folder}/datadog/{output_file}
                output_path = DATA_DIR / working_folder / DEFAULT_SUBDIR / output_file
            else:
                # Legacy path: data/datadog/{output_file}
                output_path = DATA_DIR / DEFAULT_SUBDIR / output_file

            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to JSON-serializable format
            result_data = []
            for bucket in buckets:
                bucket_dict = bucket.to_dict() if hasattr(bucket, 'to_dict') else bucket
                result_data.append(bucket_dict)

            # Save results
            with open(output_path, 'w') as f:
                json.dump({
                    "query": query,
                    "from": datetime.fromtimestamp(from_timestamp/1000).isoformat() + "Z",
                    "to": datetime.fromtimestamp(to_timestamp/1000).isoformat() + "Z",
                    "group_by": group_by,
                    "compute": f"{compute_aggregation}({compute_metric})",
                    "timeseries_interval": timeseries_interval,
                    "limit": limit,
                    "buckets_count": len(result_data),
                    "buckets": result_data
                }, f, indent=2, default=str)

            logger.info(f"✓ Results saved to: {output_path}")
            logger.info(f"  Format: JSON")

        except Exception as e:
            logger.error(f"Failed to aggregate RUM data: {e}")
            raise
