#!/usr/bin/env python3
"""RUM query functionality using Datadog API."""

import os
import json
import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.rum_api import RUMApi
from datadog_api_client.v2.model.rum_search_events_request import RUMSearchEventsRequest
from datadog_api_client.v2.model.rum_query_filter import RUMQueryFilter
from datadog_api_client.v2.model.rum_query_page_options import RUMQueryPageOptions
from datadog_api_client.v2.model.rum_sort import RUMSort
from datadog_api_client.v2.model.rum_sort_order import RUMSortOrder

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

    raise ValueError(f"Invalid time format: {time_str}. Use relative (1h, 24h, 7d), ISO (2025-01-01T00:00:00Z), or Unix timestamp")


def query_rum_data(
    query: str,
    from_time: str,
    to_time: Optional[str] = None,
    limit: int = 100,
    output_file: Optional[str] = None,
    format: str = "json",
    working_folder: Optional[str] = None
) -> None:
    """Query RUM data from Datadog API.

    Args:
        query: RUM query string (Datadog query syntax)
        from_time: Start time (relative, ISO, or Unix timestamp)
        to_time: End time (default: now)
        limit: Maximum number of results (default: 100, max: 1000)
        output_file: Output filename (e.g., "results.json")
        format: Output format (json or csv)
        working_folder: Working folder name (e.g., "2026-02-03_analysis")
    """
    # Validate limit
    if limit > 1000:
        logger.warning(f"Limit {limit} exceeds maximum of 1000. Setting to 1000.")
        limit = 1000

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

    logger.info(f"Querying RUM data...")
    logger.info(f"  Query: {query}")
    logger.info(f"  From: {datetime.fromtimestamp(from_timestamp/1000).isoformat()}Z")
    logger.info(f"  To: {datetime.fromtimestamp(to_timestamp/1000).isoformat()}Z")
    logger.info(f"  Limit: {limit}")

    # Configure Datadog API client
    configuration = Configuration()
    configuration.api_key["apiKeyAuth"] = api_key
    configuration.api_key["appKeyAuth"] = app_key
    configuration.server_variables["site"] = dd_site

    # Query RUM events
    with ApiClient(configuration) as api_client:
        api_instance = RUMApi(api_client)

        # Build search request
        body = RUMSearchEventsRequest(
            filter=RUMQueryFilter(
                query=query,
                _from=datetime.fromtimestamp(from_timestamp / 1000).isoformat() + "Z",
                to=datetime.fromtimestamp(to_timestamp / 1000).isoformat() + "Z",
            ),
            page=RUMQueryPageOptions(
                limit=limit,
            ),
        )

        try:
            response = api_instance.search_rum_events(body=body)
            events = response.data if hasattr(response, 'data') else []

            logger.info(f"✓ Retrieved {len(events)} RUM events")

            # Prepare output path

            if not output_file:
                # Auto-generated filenames
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"rum_query_{timestamp}.{format}"

            # Construct full path
            if working_folder:
                # data/{working_folder}/datadog/{output_file}
                output_path = DATA_DIR / working_folder / DEFAULT_SUBDIR / output_file
            else:
                # Legacy path: data/datadog/{output_file}
                output_path = DATA_DIR / DEFAULT_SUBDIR / output_file

            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save results
            if format == "json":
                # Convert to JSON-serializable format
                events_data = []
                for event in events:
                    event_dict = event.to_dict() if hasattr(event, 'to_dict') else event
                    events_data.append(event_dict)

                with open(output_path, 'w') as f:
                    json.dump({
                        "query": query,
                        "from": datetime.fromtimestamp(from_timestamp/1000).isoformat() + "Z",
                        "to": datetime.fromtimestamp(to_timestamp/1000).isoformat() + "Z",
                        "count": len(events_data),
                        "events": events_data
                    }, f, indent=2, default=str)

                logger.info(f"✓ Results saved to: {output_path}")
                logger.info(f"  Format: JSON")

            elif format == "csv":
                # Flatten events for CSV
                if not events:
                    logger.warning("No events to export")
                    return

                # Extract all unique fields
                all_fields = set()
                flattened_events = []

                for event in events:
                    event_dict = event.to_dict() if hasattr(event, 'to_dict') else event
                    flat_event = flatten_dict(event_dict)
                    all_fields.update(flat_event.keys())
                    flattened_events.append(flat_event)

                # Write CSV
                with open(output_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=sorted(all_fields))
                    writer.writeheader()
                    writer.writerows(flattened_events)

                logger.info(f"✓ Results saved to: {output_path}")
                logger.info(f"  Format: CSV")
                logger.info(f"  Fields: {len(all_fields)}")

        except Exception as e:
            logger.error(f"Failed to query RUM data: {e}")
            raise


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """Flatten nested dictionary for CSV export."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Convert lists to JSON strings
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))
    return dict(items)
