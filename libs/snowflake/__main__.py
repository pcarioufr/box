#!/usr/bin/env python3
"""
Make snowflake package executable as a module.

This allows running: python -m libs.snowflake [command] [args...]
"""

from .cli import main

if __name__ == '__main__':
    main()

