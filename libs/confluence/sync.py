"""Confluence sync operations.

Handles downloading Confluence pages via the Atlassian MCP server or REST API.
"""

import re
from pathlib import Path
from typing import Optional, Tuple

from libs.common.config import (
    load_config,
    save_config,
    find_confluence_entry,
    add_confluence_entry,
    extract_confluence_page_id,
    get_confluence_output_path,
    slugify,
    CONFLUENCE_OUTPUT_DIR,
)


def parse_url(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse a Confluence URL to extract cloud ID, page ID, and title hint.

    Returns:
        Tuple of (cloud_id, page_id, title_hint)
    """
    # Extract cloud ID (domain)
    cloud_match = re.search(r'https?://([^/]+)', url)
    cloud_id = cloud_match.group(1) if cloud_match else None

    # Extract page ID
    page_id = extract_confluence_page_id(url)

    # Extract title hint from URL (pages or blog)
    title_hint = None

    # Try pages pattern first
    title_match = re.search(r'/pages/\d+/([^/?]+)', url)
    if title_match:
        title_hint = title_match.group(1).replace('+', ' ').replace('%20', ' ')

    # Try blog pattern
    if not title_hint:
        title_match = re.search(r'/blog/\d{4}/\d{2}/\d{2}/\d+/([^/?]+)', url)
        if title_match:
            title_hint = title_match.group(1).replace('+', ' ').replace('%20', ' ')

    return cloud_id, page_id, title_hint


def get_entry_for_url(url: str) -> Optional[dict]:
    """Check if a URL already exists in sync config."""
    config = load_config()
    return find_confluence_entry(config, url)


def register_page(url: str, name: str) -> Tuple[dict, bool]:
    """Register a Confluence page in sync config.

    Returns:
        Tuple of (entry dict, is_new)
    """
    config = load_config()
    existing = find_confluence_entry(config, url)
    is_new = existing is None

    entry = add_confluence_entry(config, url, name)
    save_config(config)

    return entry, is_new


def save_content(entry: dict, content: str, title: Optional[str] = None) -> Path:
    """Save Confluence page content to the appropriate file."""
    name = entry.get("name", "untitled")
    output_path = get_confluence_output_path(name)

    # Add metadata header if we have a title
    if title:
        header = f"<!-- Synced from Confluence: {entry.get('url', 'unknown')} -->\n"
        header += f"<!-- Name: {name} -->\n\n"
        content = header + content

    # Write content
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


def list_entries() -> list:
    """List all Confluence entries from sync config."""
    config = load_config()
    return config.get("confluence", [])


def suggest_name_from_url(url: str) -> str:
    """Suggest a name for a Confluence page based on its URL."""
    _, _, title_hint = parse_url(url)

    if title_hint:
        return slugify(title_hint)

    # Fallback to page ID
    page_id = extract_confluence_page_id(url)
    return f"page-{page_id}" if page_id else "untitled"
