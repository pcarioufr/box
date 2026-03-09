"""Confluence URL parsing utilities."""

import re
from typing import Optional, Tuple

from libs.common.config import extract_confluence_page_id, slugify


def parse_url(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse a Confluence URL to extract domain, page ID, and title hint.

    Returns:
        Tuple of (domain, page_id, title_hint)
    """
    domain_match = re.search(r'https?://([^/]+)', url)
    domain = domain_match.group(1) if domain_match else None

    page_id = extract_confluence_page_id(url)

    # Extract title hint from URL
    title_hint = None
    title_match = re.search(r'/pages/\d+/([^/?]+)', url)
    if title_match:
        title_hint = title_match.group(1).replace('+', ' ').replace('%20', ' ')

    if not title_hint:
        title_match = re.search(r'/blog/\d{4}/\d{2}/\d{2}/\d+/([^/?]+)', url)
        if title_match:
            title_hint = title_match.group(1).replace('+', ' ').replace('%20', ' ')

    return domain, page_id, title_hint


def suggest_name_from_url(url: str) -> str:
    """Suggest a slug name for a Confluence page based on its URL."""
    _, _, title_hint = parse_url(url)

    if title_hint:
        return slugify(title_hint)

    page_id = extract_confluence_page_id(url)
    return f"page-{page_id}" if page_id else "untitled"
