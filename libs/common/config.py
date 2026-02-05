"""Sync configuration management.

Handles reading/writing sync.yaml and managing sync entries.
"""

import os
import re
from pathlib import Path
from typing import Optional
import yaml


# Project root and config paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SYNC_CONFIG_PATH = DATA_DIR / "sync.yaml"

# Fixed output directories (no custom paths)
GOOGLE_OUTPUT_DIR = DATA_DIR / "_google"
CONFLUENCE_OUTPUT_DIR = DATA_DIR / "_confluence"


def load_config() -> dict:
    """Load sync configuration from sync.yaml."""
    if not SYNC_CONFIG_PATH.exists():
        return {"google": [], "confluence": []}

    with open(SYNC_CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f) or {}

    # Ensure lists exist
    if "google" not in config or config["google"] is None:
        config["google"] = []
    if "confluence" not in config or config["confluence"] is None:
        config["confluence"] = []

    return config


def save_config(config: dict) -> None:
    """Save sync configuration to sync.yaml."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(SYNC_CONFIG_PATH, "w") as f:
        f.write("# Sync Configuration\n")
        f.write("# Docs to sync from Google Docs and Confluence.\n")
        f.write("#\n")
        f.write("# Usage:\n")
        f.write("#   ./box.sh google refresh      # Sync Google entries\n")
        f.write("#   ./box.sh confluence refresh  # Sync Confluence entries\n")
        f.write("\n")
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def extract_google_doc_id(url: str) -> Optional[str]:
    """Extract Google Doc ID from a URL."""
    # Already just an ID
    if re.match(r'^[\w-]+$', url) and len(url) > 20:
        return url

    # Google Docs URL
    match = re.search(r'docs\.google\.com/document/d/([\w-]+)', url)
    if match:
        return match.group(1)

    # Google Drive URL
    match = re.search(r'drive\.google\.com/file/d/([\w-]+)', url)
    if match:
        return match.group(1)

    return None


def extract_confluence_page_id(url: str) -> Optional[str]:
    """Extract Confluence page ID from a URL."""
    if url.isdigit():
        return url

    # Pages pattern
    match = re.search(r'/pages/(\d+)', url)
    if match:
        return match.group(1)

    # Blog pattern
    match = re.search(r'/blog/\d{4}/\d{2}/\d{2}/(\d+)', url)
    if match:
        return match.group(1)

    return None


def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^a-z0-9-]', '', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def find_google_entry(config: dict, doc_id: str) -> Optional[dict]:
    """Find a Google entry by document ID."""
    for entry in config.get("google", []):
        if entry.get("id") == doc_id:
            return entry
    return None


def find_confluence_entry(config: dict, url_or_id: str) -> Optional[dict]:
    """Find a Confluence entry by URL or page ID."""
    page_id = extract_confluence_page_id(url_or_id)

    for entry in config.get("confluence", []):
        entry_page_id = extract_confluence_page_id(entry.get("url", ""))
        if entry_page_id == page_id:
            return entry
        if entry.get("url") == url_or_id:
            return entry

    return None


def add_google_entry(config: dict, doc_id: str) -> dict:
    """Add a Google entry. Filename derived from doc title at sync time."""
    existing = find_google_entry(config, doc_id)
    entry = {"id": doc_id}

    if existing:
        idx = config["google"].index(existing)
        config["google"][idx] = entry
    else:
        config["google"].append(entry)

    return entry


def add_confluence_entry(config: dict, url: str, name: str) -> dict:
    """Add a Confluence entry."""
    existing = find_confluence_entry(config, url)
    entry = {"url": url, "name": name}

    if existing:
        idx = config["confluence"].index(existing)
        config["confluence"][idx] = entry
    else:
        config["confluence"].append(entry)

    return entry


def get_google_output_path(slug: str) -> Path:
    """Get output path for a Google doc."""
    GOOGLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return GOOGLE_OUTPUT_DIR / f"{slug}.md"


def get_confluence_output_path(name: str) -> Path:
    """Get output path for a Confluence page."""
    CONFLUENCE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return CONFLUENCE_OUTPUT_DIR / f"{name}.md"
