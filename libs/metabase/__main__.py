#!/usr/bin/env python3
"""
Make metabase package executable as a module.

This allows running: python -m libs.metabase [command] [args...]
"""

from .cli import main

if __name__ == '__main__':
    main()

