"""
Analysis Library - Statistical Analysis for Tabular Data

This package provides statistical analysis workflows for CSV data:
- compare: A/B test comparison with statistical significance testing
- analyze: Exploratory data analysis with clustering and correlations

Workflows:
    from libs.analysis import ExperimentComparison, ExploratoryAnalysis

    # A/B testing
    comparison = ExperimentComparison('entities.csv', 'metrics.yaml')
    results = comparison.run()

    # Exploratory analysis
    analysis = ExploratoryAnalysis('entities.csv', n_clusters=3)
    results = analysis.run()

Statistical Utilities:
    from libs.analysis import StatisticalAnalyzer, CorrelationAnalyzer, ClusterAnalyzer

CLI Usage:
    ./box.sh analysis compare --entities data.csv --metrics metrics.yaml
    ./box.sh analysis analyze --entities data.csv --clusters 3
"""

def __getattr__(name):
    """Lazy import of classes to avoid loading heavy dependencies at module import time."""
    if name == 'ExperimentComparison':
        from .compare import ExperimentComparison
        return ExperimentComparison
    elif name == 'ExploratoryAnalysis':
        from .analyze import ExploratoryAnalysis
        return ExploratoryAnalysis
    elif name == 'StatisticalAnalyzer':
        from .stats.statistics import StatisticalAnalyzer
        return StatisticalAnalyzer
    elif name == 'CorrelationAnalyzer':
        from .stats.correlations import CorrelationAnalyzer
        return CorrelationAnalyzer
    elif name == 'ClusterAnalyzer':
        from .stats.clustering import ClusterAnalyzer
        return ClusterAnalyzer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'ExperimentComparison',
    'ExploratoryAnalysis',
    'StatisticalAnalyzer',
    'CorrelationAnalyzer',
    'ClusterAnalyzer',
]

