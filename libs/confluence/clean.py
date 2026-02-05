"""Clean Confluence markdown by removing custom XML-like tags."""

import re
import os
from pathlib import Path
from typing import Optional


# Base output directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"


def clean_emoji_tags(text: str) -> str:
    """Convert <custom data-type="emoji">:emoji:</custom> to just :emoji:"""
    pattern = r'<custom data-type="emoji" data-id="[^"]*">([^<]+)</custom>'
    return re.sub(pattern, r'\1', text)


def clean_smartlink_tags(text: str) -> str:
    """Convert <custom data-type="smartlink">URL</custom> to [URL](URL)"""
    pattern = r'<custom data-type="smartlink" data-id="[^"]*">([^<]+)</custom>'

    def replace_smartlink(match):
        url = match.group(1)
        return f'[{url}]({url})'

    return re.sub(pattern, replace_smartlink, text)


def clean_mention_tags(text: str) -> str:
    """Convert <custom data-type="mention">@Name</custom> to just @Name"""
    pattern = r'<custom data-type="mention" data-id="[^"]*">([^<]+)</custom>'
    return re.sub(pattern, r'\1', text)


def clean_blob_images(text: str) -> str:
    """Remove or mark broken blob: image references"""
    pattern = r'!\[\]\(blob:https://[^\)]+\)'
    return re.sub(pattern, '*[Image: broken blob reference removed]*', text)


def clean_markdown(text: str) -> str:
    """Clean all Confluence-specific markup from markdown text."""
    text = clean_emoji_tags(text)
    text = clean_smartlink_tags(text)
    text = clean_mention_tags(text)
    text = clean_blob_images(text)
    return text


def clean_file(
    input_file: str,
    output_file: Optional[str] = None,
    in_place: bool = False,
    working_folder: Optional[str] = None
) -> str:
    """Clean a Confluence markdown file.

    Args:
        input_file: Path to input markdown file
        output_file: Filename for output (e.g., "cleaned.md")
        in_place: If True, overwrite the input file
        working_folder: Working folder name (e.g., "2026-02-03_analysis")

    Returns:
        Path to the output file
    """
    # Read input file
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Clean the content
    cleaned_content = clean_markdown(content)

    # Determine output path
    if in_place:
        output_path = input_file
    elif output_file and working_folder:
        output_path = DATA_DIR / working_folder / "confluence" / os.path.basename(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    elif output_file:
        output_path = output_file
    elif working_folder:
        base = os.path.basename(input_file)
        name, ext = os.path.splitext(base)
        filename = f"{name}.cleaned{ext}"
        output_path = DATA_DIR / working_folder / "confluence" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        base, ext = os.path.splitext(input_file)
        output_path = f"{base}.cleaned{ext}"

    # Write output file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)

    return str(output_path)
