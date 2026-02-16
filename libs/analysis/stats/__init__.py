"""
Statistical utilities for analysis workflows.

This subpackage provides the computational building blocks used by analysis workflows:
- StatisticalAnalyzer: Hypothesis testing (t-tests, chi-square, effect sizes)
- CorrelationAnalyzer: Correlation analysis (phi coefficient, point-biserial)
- ClusterAnalyzer: K-means clustering with silhouette optimization
"""

from .statistics import StatisticalAnalyzer
from .correlations import CorrelationAnalyzer
from .clustering import ClusterAnalyzer

__all__ = [
    'StatisticalAnalyzer',
    'CorrelationAnalyzer',
    'ClusterAnalyzer',
]
