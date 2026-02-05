#!/usr/bin/env python3
"""Fetch Jira tickets using Jira REST API v3."""

import requests
import json
import os
import sys
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Setup logging
handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[handler],
    force=True
)

# Base output directory for Jira data
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DEFAULT_SUBDIR = "jira"  # Default subdirectory for Jira outputs


def extract_text_from_adf(node: Any) -> str:
    """Recursively extract text from ADF nodes."""
    if not node or not isinstance(node, dict):
        return ""

    text_parts = []

    # Handle text nodes
    if node.get("type") == "text":
        return node.get("text", "")

    # Handle nodes with content
    if "content" in node:
        for child in node["content"]:
            child_text = extract_text_from_adf(child)
            if child_text:
                text_parts.append(child_text)

    # Join with appropriate spacing
    return " ".join(text_parts) if text_parts else ""


def convert_adf_fields(issue: Dict[str, Any]) -> None:
    """Convert ADF fields in an issue to plain text (modifies in place)."""
    if "fields" not in issue:
        return

    fields = issue["fields"]

    # Convert description field (standard field - replace in place)
    if "description" in fields and fields["description"]:
        text = extract_text_from_adf(fields["description"])
        issue["fields"]["description"] = text

    # Convert custom fields (add _text suffix)
    adf_fields = [
        'customfield_10711',  # User Story
        'customfield_10713',  # Current Workaround
        'customfield_19999',  # Customer Pain Point
        'customfield_19997',  # Business Impact Context
    ]

    for field_name in adf_fields:
        if field_name in fields and fields[field_name]:
            text = extract_text_from_adf(fields[field_name])
            issue["fields"][f"{field_name}_text"] = text


def create_clean_format(issue: Dict[str, Any], custom_fields: Optional[list] = None) -> Dict[str, Any]:
    """Convert issue to clean, human-readable format.

    Args:
        issue: Issue dictionary with fields
        custom_fields: List of custom field IDs that were requested (optional)

    Returns:
        Clean formatted issue dictionary
    """
    fields = issue.get("fields", {})

    # Mapping of custom field IDs to human-readable names
    field_mapping = {
        'customfield_10711': 'user_story',
        'customfield_10713': 'current_workaround',
        'customfield_19999': 'customer_pain_point',
        'customfield_19997': 'business_impact_context'
    }

    # Build base structure
    result = {
        "key": issue.get("key"),
        "url": f"https://datadoghq.atlassian.net/browse/{issue.get('key')}",
        "created": fields.get("created"),
        "status": fields.get("status", {}).get("name") if fields.get("status") else None,
        "summary": fields.get("summary"),
        "description": fields.get("description"),
        "org": {
            "name": fields.get("customfield_10237"),
            "id": fields.get("customfield_10236")
        }
    }

    # Build content section only if custom fields were requested
    if custom_fields:
        content = {}
        for field_id in custom_fields:
            if field_id in field_mapping:
                human_name = field_mapping[field_id]
                content[human_name] = fields.get(f"{field_id}_text")

        # Only add content section if there are any fields
        if content:
            result["content"] = content

    # Add metadata
    result["metadata"] = {
        "comments": issue.get("comment_total", 0),
        "issue_links": len(issue.get("issuelinks", []))
    }

    return result


def fetch_jira_tickets(
    project: str,
    jql: Optional[str] = None,
    custom_fields: Optional[list] = None,
    max_results: int = 100,
    output_file: Optional[str] = None,
    clean_output: bool = False,
    working_folder: Optional[str] = None
):
    """
    Fetch Jira tickets using v3 API.

    Args:
        project: Jira project key (e.g., 'FRMNTS')
        jql: Custom JQL query (optional, will default to project filter)
        custom_fields: List of custom fields to include (e.g., ['customfield_10711', 'customfield_10713'])
        max_results: Maximum number of results to fetch
        output_file: Filename to save results (e.g., "tickets.json"). Default: tickets.json
        clean_output: If True, convert to clean human-readable format (default: False)
        working_folder: Working folder name (e.g., "2026-02-03_analysis")

    Returns:
        List of issue dictionaries
    """
    # Handle output file path
    if output_file:
        # Extract just the filename, ignore any directory path
        filename = os.path.basename(output_file)
    else:
        # Default filename
        filename = "tickets.json"

    # Construct output path
    if working_folder:
        # data/{working_folder}/jira/{filename}
        output_path = DATA_DIR / working_folder / DEFAULT_SUBDIR / filename
    else:
        # Legacy path: data/jira/{filename}
        output_path = DATA_DIR / DEFAULT_SUBDIR / filename

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Get credentials from environment
    jira_email = os.getenv('ATLASSIAN_EMAIL')
    jira_token = os.getenv('ATLASSIAN_TOKEN')

    if not jira_email or not jira_token:
        raise ValueError("ATLASSIAN_EMAIL and ATLASSIAN_TOKEN environment variables must be set")

    # Setup authentication
    credentials = f"{jira_email}:{jira_token}"
    credentials_b64 = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

    # Mandatory fields always included
    mandatory_fields = [
        "summary", "description", "status", "created", "comment", "issuelinks",
        "customfield_10236",  # Org ID
        "customfield_10237"   # Org Name
    ]

    # Combine mandatory fields with custom fields
    fields = mandatory_fields.copy()
    if custom_fields:
        fields.extend(custom_fields)

    # Remove duplicates while preserving order
    fields = list(dict.fromkeys(fields))

    # Build JQL query
    if jql is None:
        jql = f"project = {project} ORDER BY created DESC"

    # API endpoint (v3 - using /search/jql as /search is deprecated)
    url = "https://datadoghq.atlassian.net/rest/api/3/search/jql"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {credentials_b64}"
    }

    all_issues = []
    start_at = 0
    results_per_page = 100

    while len(all_issues) < max_results:
        logging.info(f"Fetching results starting at {start_at}...")

        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": min(results_per_page, max_results - len(all_issues)),
            "fields": ",".join(fields)
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            logging.error(f"Failed to fetch data: {response.status_code}")
            logging.error(f"Response: {response.text}")
            break

        data = response.json()
        issues = data.get('issues', [])

        if not issues:
            logging.info("No more results - stopping")
            break

        # Simplify the structure
        for issue in issues:
            simplified_issue = {
                "id": issue["id"],
                "key": issue["key"],
                "self": issue["self"],
                "fields": issue["fields"]
            }

            # Simplify issuelinks if present
            if "issuelinks" in issue["fields"] and issue["fields"]["issuelinks"]:
                simplified_issue["issuelinks"] = [
                    {
                        "type": link["type"].get("outward", link["type"].get("inward")),
                        "key": link.get("outwardIssue", link.get("inwardIssue", {})).get("key"),
                        "summary": link.get("outwardIssue", link.get("inwardIssue", {})).get("fields", {}).get("summary")
                    }
                    for link in issue["fields"]["issuelinks"]
                ]
                # Remove from fields to avoid duplication
                del simplified_issue["fields"]["issuelinks"]

            # Simplify comments if present
            if "comment" in issue["fields"] and issue["fields"]["comment"]:
                comment_data = issue["fields"]["comment"]
                simplified_issue["comments"] = [
                    {
                        "body": comment.get("body"),
                        "created": comment.get("created"),
                        "author": comment.get("author", {}).get("displayName")
                    }
                    for comment in comment_data.get("comments", [])
                ]
                # Keep total count
                simplified_issue["comment_total"] = comment_data.get("total", 0)
                # Remove from fields to avoid duplication
                del simplified_issue["fields"]["comment"]

            # Convert ADF fields to text
            convert_adf_fields(simplified_issue)

            # Convert to clean format if requested
            if clean_output:
                simplified_issue = create_clean_format(simplified_issue, custom_fields)

            all_issues.append(simplified_issue)

        # Check if there are more results
        total = data.get('total', float('inf'))  # Default to infinity if not provided
        start_at += len(issues)

        if total != float('inf'):
            logging.info(f"Fetched {len(all_issues)} of {min(total, max_results)} issues")
        else:
            logging.info(f"Fetched {len(all_issues)} issues (total unknown)")

        # Stop if we've reached max_results or if total is known and we've fetched all
        if len(all_issues) >= max_results:
            break
        if total != float('inf') and start_at >= total:
            break

    logging.info(f"Total issues fetched: {len(all_issues)}")

    # Save to file
    with open(output_path, 'w') as f:
        json.dump(all_issues, f, indent=2)
    logging.info(f"Saved to {output_path}")

    return all_issues


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Fetch Jira tickets using v3 API',
        epilog='Mandatory fields (always included): summary, description, created, comment, issuelinks, customfield_10236 (Org ID), customfield_10237 (Org Name)'
    )
    parser.add_argument('project', help='Jira project key (e.g., FRMNTS)')
    parser.add_argument('--jql', help='Custom JQL query (optional)')
    parser.add_argument('--custom-fields', nargs='+', help='Additional custom fields to include (e.g., customfield_10711 customfield_10713)')
    parser.add_argument('--max-results', type=int, default=100, help='Maximum results to fetch')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--clean', action='store_true', help='Output clean human-readable format with converted ADF fields')

    args = parser.parse_args()

    fetch_jira_tickets(
        project=args.project,
        jql=args.jql,
        custom_fields=args.custom_fields,
        max_results=args.max_results,
        output_file=args.output,
        clean_output=args.clean
    )
