"""
Correlation Analysis - Phi Coefficient and Point-Biserial

Implements:
- Phi coefficient: binary × binary
- Point-biserial: binary × continuous
"""

from typing import Dict, Any
import numpy as np
import pandas as pd
from scipy import stats
import warnings


class CorrelationAnalyzer:
    """
    Computes correlations between entity properties.
    """
    
    def analyze(self, entities_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Compute correlations between all pairs of properties.
        
        Args:
            entities_df: Entity-level data
        
        Returns:
            Dictionary of correlation results
        """
        results = {}
        
        # Get property columns (exclude org_id, timestamps, datacenter, ID columns)
        property_cols = []
        for col in entities_df.columns:
            col_lower = col.lower()
            # Skip ID columns
            if col_lower.endswith('_id') or col_lower.startswith('id_') or col_lower == 'org_id':
                continue
            # Skip timestamp/date columns
            if 'timestamp' in col_lower or 'date' in col_lower:
                continue
            # Skip datacenter (typically not useful for correlation)
            if col_lower == 'datacenter':
                continue
            property_cols.append(col)
        
        # Calculate total pairs for progress tracking
        n_cols = len(property_cols)
        total_pairs = n_cols * (n_cols - 1) // 2
        pairs_processed = 0
        pairs_skipped = 0  # Track constant variables
        
        # Compute correlations for all pairs
        for i, col1 in enumerate(property_cols):
            for col2 in property_cols[i+1:]:  # Only unique pairs
                pairs_processed += 1
                if total_pairs > 10:  # Only show progress if meaningful
                    print(f"      Computing correlations: {pairs_processed}/{total_pairs} pairs...", end='\r')
                # Get data
                data1 = entities_df[col1].dropna()
                data2 = entities_df[col2].dropna()
                
                # Need common indices
                common_idx = data1.index.intersection(data2.index)
                if len(common_idx) < 10:  # Need minimum sample
                    continue
                
                data1 = data1.loc[common_idx]
                data2 = data2.loc[common_idx]
                
                # Skip if either variable is constant (zero variance)
                if data1.nunique() <= 1 or data2.nunique() <= 1:
                    pairs_skipped += 1
                    continue
                
                # Detect types
                type1 = self._detect_type(data1)
                type2 = self._detect_type(data2)
                
                # Compute appropriate correlation (suppress scipy constant warnings)
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', message='.*constant.*', category=RuntimeWarning)
                    
                    if type1 == 'binary' and type2 == 'binary':
                        corr_result = self._phi_coefficient(data1, data2)
                        corr_result['type'] = 'phi_coefficient'
                    
                    elif (type1 == 'binary' and type2 == 'continuous') or \
                         (type1 == 'continuous' and type2 == 'binary'):
                        corr_result = self._point_biserial(data1, data2, type1, type2)
                        corr_result['type'] = 'point_biserial'
                    
                    else:
                        # Continuous × continuous: Phase 2 feature
                        continue
                
                # Skip if result is NaN (constant variable edge case)
                if pd.isna(corr_result.get('value')):
                    pairs_skipped += 1
                    continue
                
                # Add to results
                key = f"{col1}_x_{col2}"
                results[key] = corr_result
        
        if total_pairs > 10:
            print()  # Clear progress line
        
        # Report skipped pairs if any
        if pairs_skipped > 0:
            print(f"      (Skipped {pairs_skipped} pairs with constant variables)")
        
        return results
    
    def _detect_type(self, series: pd.Series) -> str:
        """Detect if series is binary or continuous."""
        unique_vals = series.unique()
        if len(unique_vals) <= 2 and set(unique_vals).issubset({0, 1, 0.0, 1.0}):
            return 'binary'
        return 'continuous'
    
    def _phi_coefficient(self, data1: pd.Series, data2: pd.Series) -> Dict[str, Any]:
        """
        Compute phi coefficient for binary × binary.
        
        Phi coefficient is equivalent to Pearson correlation for binary variables.
        """
        # Create contingency table
        contingency = pd.crosstab(data1, data2)
        
        # Ensure 2x2 table
        if contingency.shape != (2, 2):
            return {'value': 0.0, 'p_value': 1.0, 'n': len(data1)}
        
        # Phi coefficient
        n = len(data1)
        chi2 = stats.chi2_contingency(contingency)[0]
        phi = np.sqrt(chi2 / n)
        
        # P-value from chi-square test
        _, p_value, _, _ = stats.chi2_contingency(contingency)
        
        # Sign of phi (positive if both tend to be 1 together)
        if contingency.iloc[1, 1] * contingency.iloc[0, 0] < \
           contingency.iloc[1, 0] * contingency.iloc[0, 1]:
            phi = -phi
        
        return {
            'value': round(float(phi), 6),  # 6 decimal places for precision
            'p_value': round(float(p_value), 3),  # 3 decimal places for p-values
            'n': int(n)
        }
    
    def _point_biserial(
        self,
        data1: pd.Series,
        data2: pd.Series,
        type1: str,
        type2: str
    ) -> Dict[str, Any]:
        """
        Compute point-biserial correlation for binary × continuous.
        """
        # Ensure data1 is binary, data2 is continuous
        if type1 == 'continuous':
            data1, data2 = data2, data1
        
        # Point-biserial correlation
        r, p_value = stats.pointbiserialr(data1, data2)
        
        return {
            'value': round(float(r), 6),  # 6 decimal places for precision
            'p_value': round(float(p_value), 3),  # 3 decimal places for p-values
            'n': len(data1)
        }

