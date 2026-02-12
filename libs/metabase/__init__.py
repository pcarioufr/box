"""
Metabase Integration

Sync dashboards and questions between Metabase and local state.

Usage as CLI:
    python -m libs.metabase pull
    python -m libs.metabase push --question-id 90926
"""

from .cli import main as cli_main

__version__ = '1.0.0'
__all__ = ['cli_main']

