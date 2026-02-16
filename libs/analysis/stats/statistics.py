"""
Statistical Analysis - Tests, Effect Sizes, Confidence Intervals

Implements:
- Binary metrics: Chi-square test, Fisher's exact
- Continuous metrics: T-test, Mann-Whitney U  
- Effect sizes: Relative lift, Cohen's d, absolute difference
- Confidence intervals: 95% (configurable)
"""

import re
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import chi2_contingency, fisher_exact, ttest_ind, mannwhitneyu


class StatisticalAnalyzer:
    """
    Performs statistical analysis on experiment metrics.
    """
    
    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize analyzer.
        
        Args:
            confidence_level: Confidence level for intervals (default 0.95)
        """
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
    
    def analyze(self, entities_df: pd.DataFrame, metrics_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze all metrics.
        
        Args:
            entities_df: Entity-level data
            metrics_df: Aggregated metrics (2 rows: blue and green)
        
        Returns:
            Dictionary of metric results
        """
        results = {}
        
        # Get all metric columns (exclude 'variant' and 'sample_size')
        metric_cols = [col for col in metrics_df.columns 
                      if col not in ['variant', 'sample_size']]
        
        for metric_name in metric_cols:
            print(f"      Analyzing {metric_name}...")
            
            # Get values for blue and green
            blue_row = metrics_df[metrics_df['variant'] == 'blue']
            green_row = metrics_df[metrics_df['variant'] == 'green']
            
            if len(blue_row) == 0 or len(green_row) == 0:
                print(f"      ⚠️  Skipping {metric_name}: missing variant data")
                continue
            
            # Get entity-level data for this metric
            metric_property = self._infer_property_name(metric_name, entities_df)
            if metric_property is None:
                print(f"      ⚠️  Skipping {metric_name}: cannot find source property")
                continue
            
            # Detect metric type
            metric_type = self._detect_metric_type(entities_df[metric_property])
            
            # Run appropriate test
            if metric_type == 'binary':
                result = self._analyze_binary_metric(
                    metric_name, metric_property, entities_df
                )
            else:  # continuous
                result = self._analyze_continuous_metric(
                    metric_name, metric_property, entities_df
                )
            
            # Only add if result is not None (can be None if variant is empty)
            if result is not None:
                results[metric_name] = result
        
        return results
    
    def analyze_with_config(
        self,
        entities_df: pd.DataFrame,
        metrics_df: pd.DataFrame,
        metrics_config: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze metrics using explicit configuration.
        
        Args:
            entities_df: Entity-level data
            metrics_df: Aggregated metrics (2 rows: blue and green)
            metrics_config: Mapping of metric_name -> {source, type, description, ...}
        
        Returns:
            Dictionary of metric results
        """
        results = {}
        
        for metric_name, metric_def in metrics_config.items():
            print(f"      Analyzing {metric_name}...")
            
            # Get source property from config (explicit, no inference!)
            property_name = metric_def['source']
            
            # Validate property exists
            if property_name not in entities_df.columns:
                print(f"      ⚠️  Skipping {metric_name}: source '{property_name}' not found")
                continue
            
            # Detect metric type from entity data
            metric_type = self._detect_metric_type(entities_df[property_name])
            
            # Run appropriate test
            if metric_type == 'binary':
                result = self._analyze_binary_metric(
                    metric_name, property_name, entities_df
                )
            else:  # continuous
                result = self._analyze_continuous_metric(
                    metric_name, property_name, entities_df
                )
            
            if result is not None:
                results[metric_name] = result
        
        return results
    
    def _detect_metric_type(self, series: pd.Series) -> str:
        """
        Detect if metric is binary or continuous.
        
        Binary: Only values are 0 and 1, or 2 unique non-numeric values (e.g., 'yes'/'no')
        Continuous: Range of numeric values
        """
        unique_vals = series.dropna().unique()
        
        # Check if numeric binary (0/1)
        if len(unique_vals) <= 2 and set(unique_vals).issubset({0, 1, 0.0, 1.0}):
            return 'binary'
        
        # Check if boolean
        if pd.api.types.is_bool_dtype(series):
            return 'binary'
        
        # Check if string/categorical with 2 unique values (binary)
        if len(unique_vals) <= 2 and not pd.api.types.is_numeric_dtype(series):
            return 'binary'
        
        # Otherwise continuous
        return 'continuous'
    
    def _analyze_binary_metric(
        self, 
        metric_name: str,
        property_name: str, 
        entities_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Analyze a binary metric (proportion/rate).
        
        Uses chi-square test or Fisher's exact for small samples.
        """
        # Get data by variant
        blue_data = entities_df[entities_df['variant'] == 'blue'][property_name].dropna()
        green_data = entities_df[entities_df['variant'] == 'green'][property_name].dropna()
        
        # Counts
        n_blue = len(blue_data)
        n_green = len(green_data)
        
        # Check for empty groups
        if n_blue == 0 or n_green == 0:
            print(f"      ⚠️  Skipping {metric_name}: empty variant (n_blue={n_blue}, n_green={n_green})")
            return None
        
        # Convert to numeric if needed (handle string binary columns)
        if pd.api.types.is_numeric_dtype(blue_data) or pd.api.types.is_bool_dtype(blue_data):
            success_blue = int(blue_data.sum())
            success_green = int(green_data.sum())
        else:
            # String binary column - find "truthy" values
            unique_vals = sorted(pd.concat([blue_data, green_data]).unique())
            if len(unique_vals) > 2:
                raise ValueError(f"Binary metric '{metric_name}' has >2 unique values")
            # Assume second value alphabetically is "positive" (e.g., 'yes' > 'no')
            positive_val = unique_vals[-1] if len(unique_vals) > 1 else unique_vals[0]
            success_blue = int((blue_data == positive_val).sum())
            success_green = int((green_data == positive_val).sum())
        
        # Rates
        rate_blue = success_blue / n_blue if n_blue > 0 else 0
        rate_green = success_green / n_green if n_green > 0 else 0
        
        # Contingency table for chi-square
        # [[success_blue, fail_blue], [success_green, fail_green]]
        contingency = np.array([
            [success_blue, n_blue - success_blue],
            [success_green, n_green - success_green]
        ])
        
        # Statistical test
        if n_blue < 30 or n_green < 30:
            # Use Fisher's exact for small samples
            _, p_value = fisher_exact(contingency)
            test_name = 'fisher_exact'
        else:
            # Use chi-square for large samples
            chi2, p_value, _, _ = chi2_contingency(contingency)
            test_name = 'chi_square'
        
        # Effect sizes
        relative_lift = (rate_green - rate_blue) / rate_blue if rate_blue > 0 else float('inf')
        absolute_diff = rate_green - rate_blue
        
        # Confidence interval for difference in proportions
        ci_lower, ci_upper = self._proportion_diff_ci(
            success_blue, n_blue, success_green, n_green
        )
        
        return {
            'type': 'binary',
            'blue': {
                'rate': float(rate_blue),
                'count': success_blue,
                'n': n_blue
            },
            'green': {
                'rate': float(rate_green),
                'count': success_green,
                'n': n_green
            },
            'statistics': {
                'test': test_name,
                'p_value': float(p_value),
                f'confidence_interval_{int(self.confidence_level * 100)}': [
                    float(ci_lower), float(ci_upper)
                ],
                'effect_size': {
                    'relative_lift': float(relative_lift) if np.isfinite(relative_lift) else None,
                    'absolute_difference': float(absolute_diff)
                }
            },
            'significant': bool(p_value < self.alpha)
        }
    
    def _analyze_continuous_metric(
        self,
        metric_name: str,
        property_name: str,
        entities_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Analyze a continuous metric (mean/average).
        
        Uses t-test or Mann-Whitney U.
        """
        # Get data by variant
        blue_data = entities_df[entities_df['variant'] == 'blue'][property_name].dropna()
        green_data = entities_df[entities_df['variant'] == 'green'][property_name].dropna()
        
        # Descriptive stats
        n_blue = len(blue_data)
        n_green = len(green_data)
        
        # Check for empty groups
        if n_blue == 0 or n_green == 0:
            print(f"      ⚠️  Skipping {metric_name}: empty variant (n_blue={n_blue}, n_green={n_green})")
            return None
        
        mean_blue = float(blue_data.mean())
        mean_green = float(green_data.mean())
        std_blue = float(blue_data.std())
        std_green = float(green_data.std())
        
        # Check normality (Shapiro-Wilk test)
        _, p_norm_blue = stats.shapiro(blue_data) if n_blue < 5000 else (None, 1.0)
        _, p_norm_green = stats.shapiro(green_data) if n_green < 5000 else (None, 1.0)
        
        # Choose test based on normality
        if p_norm_blue > 0.05 and p_norm_green > 0.05:
            # Both normal: use t-test
            t_stat, p_value = ttest_ind(blue_data, green_data)
            test_name = 't_test'
        else:
            # Non-normal: use Mann-Whitney U
            u_stat, p_value = mannwhitneyu(blue_data, green_data, alternative='two-sided')
            test_name = 'mann_whitney_u'
        
        # Effect sizes
        cohens_d = (mean_green - mean_blue) / np.sqrt((std_blue**2 + std_green**2) / 2)
        pct_diff = (mean_green - mean_blue) / mean_blue if mean_blue != 0 else float('inf')
        mean_diff = mean_green - mean_blue
        
        # Confidence interval for mean difference
        ci_lower, ci_upper = self._mean_diff_ci(
            blue_data, green_data
        )
        
        return {
            'type': 'continuous',
            'blue': {
                'mean': mean_blue,
                'std': std_blue,
                'n': n_blue
            },
            'green': {
                'mean': mean_green,
                'std': std_green,
                'n': n_green
            },
            'statistics': {
                'test': test_name,
                'p_value': float(p_value),
                f'confidence_interval_{int(self.confidence_level * 100)}': [
                    float(ci_lower), float(ci_upper)
                ],
                'effect_size': {
                    'cohens_d': float(cohens_d) if np.isfinite(cohens_d) else None,
                    'percent_difference': float(pct_diff) if np.isfinite(pct_diff) else None,
                    'mean_difference': float(mean_diff)
                }
            },
            'significant': bool(p_value < self.alpha)
        }
    
    def _proportion_diff_ci(
        self,
        x1: int, n1: int,
        x2: int, n2: int
    ) -> Tuple[float, float]:
        """
        Confidence interval for difference in proportions.
        
        Uses normal approximation.
        """
        p1 = x1 / n1 if n1 > 0 else 0
        p2 = x2 / n2 if n2 > 0 else 0
        
        diff = p2 - p1
        se = np.sqrt((p1 * (1 - p1) / n1) + (p2 * (1 - p2) / n2))
        
        z = stats.norm.ppf(1 - self.alpha / 2)
        ci_lower = diff - z * se
        ci_upper = diff + z * se
        
        return ci_lower, ci_upper
    
    def _mean_diff_ci(
        self,
        data1: pd.Series,
        data2: pd.Series
    ) -> Tuple[float, float]:
        """
        Confidence interval for difference in means.
        
        Uses t-distribution.
        """
        n1 = len(data1)
        n2 = len(data2)
        mean1 = data1.mean()
        mean2 = data2.mean()
        var1 = data1.var()
        var2 = data2.var()
        
        # Pooled standard error
        se = np.sqrt(var1 / n1 + var2 / n2)
        
        # Degrees of freedom (Welch's approximation)
        df = (var1 / n1 + var2 / n2)**2 / (
            (var1 / n1)**2 / (n1 - 1) + (var2 / n2)**2 / (n2 - 1)
        )
        
        # T critical value
        t_crit = stats.t.ppf(1 - self.alpha / 2, df)
        
        diff = mean2 - mean1
        ci_lower = diff - t_crit * se
        ci_upper = diff + t_crit * se
        
        return ci_lower, ci_upper

