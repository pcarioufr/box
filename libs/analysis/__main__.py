#!/usr/bin/env python3
"""
Make analysis package executable as a module.

This allows running: python -m libs.analysis [command] [args...]
"""

import sys


def print_help():
    """Print main help message."""
    help_text = """
analysis - Statistical analysis for tabular data

Usage:
  analysis compare --entities <csv> --metrics <yaml> [options]
  analysis analyze --entities <csv> [options]

Commands:
  compare    A/B test comparison with statistical significance testing
             - Input: Entities CSV (with 'variant' column) + Metrics YAML
             - Output: Statistical tests, effect sizes, confidence intervals, correlations
             - Tests: t-tests, chi-square, Fisher's exact, Mann-Whitney U

  analyze    Exploratory data analysis with k-means clustering
             - Input: Entities CSV (numeric/binary features)
             - Output: Cluster profiles, distributions, correlations
             - Features: Auto-detect optimal k, binary encoding, correlation matrix

Quick Start:
  # A/B test comparison
  analysis compare --entities experiment.csv --metrics metrics.yaml

  # Exploratory analysis (auto-detect clusters)
  analysis analyze --entities customer_data.csv

  # Exploratory analysis (specify clusters)
  analysis analyze --entities customer_data.csv --clusters 4

Common Options:
  --output <path>     Custom output file path (default: output.yaml)
  --null <strategy>   NULL handling: per-metric, per-entity, error (compare only)
  --clusters <n>      Number of clusters (analyze only, default: auto-detect)
  --sampling <rate>   Sample rate for k-selection (analyze only, e.g., 10 = 1/10th)
  --debug             Include detailed statistics in output (analyze only)

For detailed help:
  analysis compare --help    # Show input formats, examples, NULL strategies
  analysis analyze --help    # Show feature detection, clustering, examples

Architecture:
  Workflows (compare.py, analyze.py) - High-level orchestration
  Stats utilities (stats/)            - Reusable building blocks

Full documentation: libs/analysis/README.md
"""
    print(help_text)


def main():
    """Main CLI entry point with command routing."""

    # If no arguments or help requested, show help
    if len(sys.argv) == 1 or sys.argv[1] in ['-h', '--help', 'help']:
        print_help()
        sys.exit(0)

    # Get the first argument (command)
    command = sys.argv[1]

    # Remove command from argv so subcommands see clean args
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    # Route to appropriate workflow (import only when needed)
    if command == 'compare':
        from . import compare
        compare.main()
    elif command == 'analyze':
        from . import analyze
        analyze.main()
    else:
        print(f"Error: Unknown command '{command}'", file=sys.stderr)
        print("", file=sys.stderr)
        print("Available commands:", file=sys.stderr)
        print("  compare    - A/B test comparison", file=sys.stderr)
        print("  analyze    - Exploratory data analysis", file=sys.stderr)
        print("", file=sys.stderr)
        print("Use --help for more information.", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

