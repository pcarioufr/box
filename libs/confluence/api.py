"""Confluence REST API client for direct page/blogpost fetching.

This module bypasses MCP and uses the Confluence REST API v2 directly,
enabling access to both pages and blog posts with proper authentication.
"""

import os
import re
import base64
import html
from pathlib import Path
from typing import Optional, Tuple
import requests

from libs.common.config import (
    extract_confluence_page_id,
    get_confluence_output_path,
)


def get_credentials() -> Tuple[str, str]:
    """Get Atlassian credentials from environment.

    Returns:
        Tuple of (email, api_token)

    Raises:
        ValueError: If credentials are not configured
    """
    email = os.environ.get("ATLASSIAN_EMAIL")
    token = os.environ.get("ATLASSIAN_TOKEN")

    if not email or not token:
        raise ValueError(
            "ATLASSIAN_EMAIL and ATLASSIAN_TOKEN must be set in .env\n"
            "See env.example for setup instructions."
        )

    return email, token


def get_auth_header(email: str, token: str) -> dict:
    """Create Basic Auth header for Atlassian API."""
    credentials = f"{email}:{token}"
    b64_credentials = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {b64_credentials}"}


def detect_content_type(url: str) -> str:
    """Detect if URL is a page or blog post."""
    if "/blog/" in url:
        return "blogpost"
    return "page"


def extract_cloud_domain(url: str) -> str:
    """Extract the Atlassian domain from URL."""
    match = re.search(r'https?://([^/]+)', url)
    if match:
        return match.group(1)
    return "datadoghq.atlassian.net"


def fetch_page(domain: str, page_id: str, body_format: str = "storage") -> dict:
    """Fetch a Confluence page via REST API v2."""
    email, token = get_credentials()

    url = f"https://{domain}/wiki/api/v2/pages/{page_id}"
    params = {"body-format": body_format}

    response = requests.get(
        url,
        params=params,
        headers=get_auth_header(email, token),
        timeout=30
    )
    response.raise_for_status()

    return response.json()


def fetch_blogpost(domain: str, blogpost_id: str, body_format: str = "storage") -> dict:
    """Fetch a Confluence blog post via REST API v2."""
    email, token = get_credentials()

    url = f"https://{domain}/wiki/api/v2/blogposts/{blogpost_id}"
    params = {"body-format": body_format}

    response = requests.get(
        url,
        params=params,
        headers=get_auth_header(email, token),
        timeout=30
    )
    response.raise_for_status()

    return response.json()


def fetch_content(url: str, body_format: str = "storage") -> dict:
    """Fetch any Confluence content (page or blogpost) by URL."""
    domain = extract_cloud_domain(url)
    page_id = extract_confluence_page_id(url)
    content_type = detect_content_type(url)

    if not page_id:
        raise ValueError(f"Could not extract page ID from URL: {url}")

    if content_type == "blogpost":
        return fetch_blogpost(domain, page_id, body_format)
    else:
        return fetch_page(domain, page_id, body_format)


def storage_to_markdown(storage_html: str) -> str:
    """Convert Confluence storage format to markdown."""
    text = storage_html

    # Handle headings
    for i in range(6, 0, -1):
        text = re.sub(
            rf'<h{i}[^>]*>(.*?)</h{i}>',
            lambda m: '#' * i + ' ' + m.group(1).strip() + '\n\n',
            text,
            flags=re.DOTALL | re.IGNORECASE
        )

    # Handle paragraphs
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)

    # Handle bold
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text, flags=re.DOTALL)

    # Handle italic
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)
    text = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', text, flags=re.DOTALL)

    # Handle links
    text = re.sub(
        r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        r'[\2](\1)',
        text,
        flags=re.DOTALL
    )

    # Handle unordered lists
    text = re.sub(r'<ul[^>]*>', '\n', text)
    text = re.sub(r'</ul>', '\n', text)
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL)

    # Handle ordered lists (simplified)
    text = re.sub(r'<ol[^>]*>', '\n', text)
    text = re.sub(r'</ol>', '\n', text)

    # Handle code blocks
    text = re.sub(
        r'<ac:structured-macro[^>]*ac:name="code"[^>]*>.*?<ac:plain-text-body><!\[CDATA\[(.*?)\]\]></ac:plain-text-body>.*?</ac:structured-macro>',
        r'```\n\1\n```\n',
        text,
        flags=re.DOTALL
    )

    # Handle inline code
    text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)

    # Handle blockquotes
    text = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', r'> \1\n', text, flags=re.DOTALL)

    # Handle line breaks
    text = re.sub(r'<br\s*/?>', '\n', text)

    # Handle horizontal rules
    text = re.sub(r'<hr\s*/?>', '\n---\n', text)

    # Handle tables (basic conversion)
    text = re.sub(r'<table[^>]*>', '\n', text)
    text = re.sub(r'</table>', '\n', text)
    text = re.sub(r'<tr[^>]*>', '', text)
    text = re.sub(r'</tr>', ' |\n', text)
    text = re.sub(r'<t[hd][^>]*>(.*?)</t[hd]>', r'| \1 ', text, flags=re.DOTALL)

    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    text = html.unescape(text)

    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text


def download_content(url: str, name: str, as_markdown: bool = True) -> Tuple[Path, str]:
    """Download Confluence content and save to file.

    Args:
        url: Full Confluence URL
        name: Name for the output file (without .md)
        as_markdown: If True, convert to markdown; otherwise save raw storage format

    Returns:
        Tuple of (output_path, title)
    """
    # Fetch content
    data = fetch_content(url, body_format="storage")

    # Extract body and title
    title = data.get("title", "Untitled")
    body_key = "storage" if "storage" in data.get("body", {}) else "view"
    body = data.get("body", {}).get(body_key, {}).get("value", "")

    # Convert to markdown if requested
    if as_markdown:
        content = storage_to_markdown(body)
    else:
        content = body

    # Add header
    header = f"<!-- Synced from Confluence: {url} -->\n"
    header += f"<!-- Title: {title} -->\n\n"
    header += f"# {title}\n\n"
    content = header + content

    # Save to file
    output_path = get_confluence_output_path(name)
    output_path.write_text(content, encoding="utf-8")

    return output_path, title
