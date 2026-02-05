"""
Snowflake utilities for onboarding-analytics

This package provides tools for executing Snowflake queries:
- query: Execute SQL queries from files with template variable support

Usage as CLI:
    python -m libs.snowflake query <sql-file> [options]
    
Usage programmatically:
    from libs.snowflake import connect, execute_query, load_query
"""

from .query import (
    connect,
    execute_query,
    load_query,
    preprocess_query,
    save_as_csv,
)
from .cli import main as cli_main

__all__ = [
    'connect',
    'execute_query',
    'load_query',
    'preprocess_query',
    'save_as_csv',
    'cli_main',
]

