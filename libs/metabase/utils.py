#!/usr/bin/env python3
"""
Metabase shared utilities and configuration.

Provides shared configuration loading, API request handling, color palette management,
and common utilities.
"""

import json
import os
import urllib.request
import urllib.error
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


# =============================================================================
# Environment & Configuration
# =============================================================================

def load_env():
    """Load environment variables from .env file if it exists."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Strip quotes from value if present
                    value = value.strip()
                    if value and value[0] in ['"', "'"] and value[-1] == value[0]:
                        value = value[1:-1]
                    # Don't override existing environment variables
                    if key not in os.environ:
                        os.environ[key] = value


def get_metabase_config() -> Dict[str, str]:
    """
    Get Metabase configuration from environment variables.
    
    Returns:
        Dictionary with url and api_key
    
    Raises:
        ValueError: If required config is missing
    """
    load_env()
    
    url = os.getenv("METABASE_URL")
    api_key = os.getenv("METABASE_API_KEY")
    
    if not api_key:
        raise ValueError(
            "METABASE_API_KEY not set.\n"
            "Please set it in your .env file or as an environment variable."
        )
    
    return {
        "url": url,
        "api_key": api_key
    }


def get_state_dir() -> Path:
    """
    Get the default output directory path.
    
    Returns:
        Path object for the default output directory (knowledge/questions/)
    """
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent  # Go up to repo root
    output_dir = repo_root / "knowledge" / "questions"
    
    # Create directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    return output_dir


# =============================================================================
# API Requests
# =============================================================================

def api_request(url: str, api_key: str, method: str = "GET", data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Make an authenticated request to the Metabase API.
    
    Args:
        url: The API endpoint URL
        api_key: The Metabase API key
        method: HTTP method (GET, POST, PUT, etc.)
        data: Data to send (for POST/PUT)
    
    Returns:
        Parsed JSON response
    
    Raises:
        urllib.error.HTTPError: If the request fails
    """
    import ssl
    
    request = urllib.request.Request(url, method=method)
    request.add_header("X-API-KEY", api_key)
    request.add_header("Content-Type", "application/json")
    
    if data is not None:
        request.data = json.dumps(data).encode('utf-8')
    
    # Create SSL context that's compatible with various server configurations
    ssl_context = ssl.create_default_context()
    
    try:
        with urllib.request.urlopen(request, timeout=30, context=ssl_context) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        # Try to read error response body for more details
        try:
            error_body = e.read().decode('utf-8')
            try:
                error_data = json.loads(error_body)
                error_message = error_data.get('message', error_data.get('errors', str(error_data)))
            except json.JSONDecodeError:
                error_message = error_body
            
            # Create a new exception with the detailed message
            new_error = urllib.error.HTTPError(e.url, e.code, f"{e.reason}: {error_message}", e.hdrs, None)
            raise new_error from e
        except Exception as parse_error:
            # If we can't parse the error, re-raise original
            raise e from None


# =============================================================================
# Color Palette Management
# =============================================================================

_COLOR_CACHE = None
_REVERSE_COLOR_CACHE = None


def load_color_config() -> Dict[str, str]:
    """
    Load color palette configuration from config.yaml.
    
    Returns a flat dictionary mapping color names to hex codes.
    Example: {"blue1": "#015ac1", "blue2": "#5073ce", ...}
    """
    global _COLOR_CACHE
    
    if _COLOR_CACHE is not None:
        return _COLOR_CACHE
    
    config_path = Path(__file__).parent / "config.yaml"
    
    if not config_path.exists():
        _COLOR_CACHE = {}
        return _COLOR_CACHE
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Flatten the nested palette structure
    colors = {}
    palettes = config.get('colors', {}).get('palettes', {})
    
    for palette_name, palette_colors in palettes.items():
        for color_name, hex_code in palette_colors.items():
            colors[color_name] = hex_code
    
    _COLOR_CACHE = colors
    return colors


def load_reverse_color_map() -> Dict[str, str]:
    """
    Load reverse color map (hex code -> color name).
    
    Returns a dictionary mapping hex codes to color names.
    Example: {"#015ac1": "blue1", "#5073ce": "blue2", ...}
    
    Note: If multiple color names map to the same hex code,
    the last one wins (arbitrary but consistent).
    """
    global _REVERSE_COLOR_CACHE
    
    if _REVERSE_COLOR_CACHE is not None:
        return _REVERSE_COLOR_CACHE
    
    color_map = load_color_config()
    
    # Reverse the mapping (hex -> name)
    # Normalize hex codes to lowercase for consistent matching
    reverse_map = {}
    for name, hex_code in color_map.items():
        normalized_hex = hex_code.lower()
        reverse_map[normalized_hex] = name
    
    _REVERSE_COLOR_CACHE = reverse_map
    return reverse_map


def resolve_color_to_hex(color_value: str) -> str:
    """
    Convert a color name or hex code to a hex code.
    
    Args:
        color_value: Either a color name (e.g., "blue2") or hex code (e.g., "#015ac1")
    
    Returns:
        Hex code. If input is already a hex code, returns it unchanged.
        If input is a color name, returns the corresponding hex code.
        If color name not found, returns the input unchanged (assume custom hex).
    
    Examples:
        resolve_color_to_hex("blue2") -> "#5073ce"
        resolve_color_to_hex("#509EE3") -> "#509EE3"
        resolve_color_to_hex("custom-color") -> "custom-color" (not found, pass through)
    """
    # If it starts with #, assume it's already a hex code
    if color_value.startswith('#'):
        return color_value
    
    # Try to resolve as a color name
    color_map = load_color_config()
    return color_map.get(color_value, color_value)


def resolve_hex_to_color(hex_code: str) -> str:
    """
    Convert a hex code to a color name if it exists in the palette.
    
    Args:
        hex_code: Hex color code (e.g., "#5073ce")
    
    Returns:
        Color name if found in palette (e.g., "blue2"), otherwise returns hex code unchanged.
    
    Examples:
        resolve_hex_to_color("#5073ce") -> "blue2"
        resolve_hex_to_color("#509EE3") -> "#509EE3" (not in palette)
    """
    # Normalize to lowercase for matching
    normalized_hex = hex_code.lower()
    
    reverse_map = load_reverse_color_map()
    return reverse_map.get(normalized_hex, hex_code)


def convert_colors_in_dict(data: dict, direction: str = 'to_hex') -> dict:
    """
    Recursively convert color values in a dictionary.
    
    Args:
        data: Dictionary potentially containing color values
        direction: 'to_hex' to convert names to hex codes,
                  'to_name' to convert hex codes to names
    
    Returns:
        Dictionary with converted color values
    """
    if not isinstance(data, dict):
        return data
    
    result = {}
    
    for key, value in data.items():
        # Check if this key is likely a color field
        is_color_field = 'color' in key.lower()
        
        if is_color_field and isinstance(value, str):
            if direction == 'to_hex':
                result[key] = resolve_color_to_hex(value)
            else:  # to_name
                result[key] = resolve_hex_to_color(value)
        elif isinstance(value, dict):
            result[key] = convert_colors_in_dict(value, direction)
        elif isinstance(value, list):
            result[key] = [
                convert_colors_in_dict(item, direction) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


# =============================================================================
# Utility Functions
# =============================================================================

def slugify(text: str) -> str:
    """
    Convert text to a URL-friendly slug.
    
    Args:
        text: Text to slugify
    
    Returns:
        Slugified text
    """
    import re
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    return text


