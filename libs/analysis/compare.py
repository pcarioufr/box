#!/usr/bin/env python3
"""
Experiment Comparison - Statistical Analysis for A/B Tests

Compares two experiment variants (blue vs green) with statistical significance testing.

Usage:
    ./box.sh analysis compare --entities entities.csv --metrics metrics.yaml [options]
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
import yaml

# Import statistical utilities
from .stats.statistics import StatisticalAnalyzer
from .stats.correlations import CorrelationAnalyzer


class ExperimentComparison:
    """
    High-level orchestrator for experiment comparison.
    
    Coordinates the analysis pipeline:
    1. Execute SQL queries (via libs.snowflake)
    2. Validate data structure
    3. Run statistical tests (via libs.experiment.statistics)
    4. Compute correlations (via libs.experiment.correlations)
    5. Generate output
    """
    
    def __init__(
        self,
        entities_csv: str,
        metrics_config: str,
        null_handling: str = "per-metric",
        confidence_level: float = 0.95
    ):
        """
        Initialize the comparison.

        Args:
            entities_csv: Path to entities CSV file
            metrics_config: Path to metrics YAML configuration file
            null_handling: How to handle NULLs ('per-metric', 'per-entity', 'error')
            confidence_level: Confidence level for intervals (default 0.95)
        """
        self.entities_csv = Path(entities_csv)
        self.metrics_config = Path(metrics_config)
        self.null_handling = null_handling
        self.confidence_level = confidence_level

        # Initialize analyzers
        self.stats_analyzer = StatisticalAnalyzer(confidence_level=confidence_level)
        self.corr_analyzer = CorrelationAnalyzer()
        
    def run(self) -> Dict[str, Any]:
        """
        Run the complete analysis pipeline.
        
        Returns:
            Dictionary with analysis results
        """
        print(f"\n{'='*100}")
        print("EXPERIMENT ANALYSIS")
        print(f"{'='*100}\n")
        
        # Step 1: Load CSV data and metrics config
        print("📊 Step 1: Loading data and metrics configuration...")
        entities_df, metrics_df, metrics_config = self._load_data()
        print(f"   ✓ Entities loaded: {len(entities_df)} rows")
        print(f"   ✓ Metrics computed: {len(metrics_config)} metrics\n")
        
        # Step 2: Validate data structure
        print("🔍 Step 2: Validating data structure...")
        self._validate_data(entities_df, metrics_df)
        print("   ✓ Data structure valid\n")
        
        # Step 3: Handle NULLs
        print(f"🧹 Step 3: Handling NULLs (strategy: {self.null_handling})...")
        entities_df = self._handle_nulls(entities_df)
        print("   ✓ NULLs handled\n")
        
        # Step 4: Run statistical tests
        print("📈 Step 4: Running statistical tests...")
        statistics = self.stats_analyzer.analyze_with_config(entities_df, metrics_df, metrics_config)
        print(f"   ✓ Analyzed {len(statistics)} metrics\n")
        
        # Step 5: Identify and encode properties
        print("🔍 Step 5: Identifying properties...")
        property_cols, excluded_cols, binary_encodings, entities_encoded = self._identify_properties(entities_df)
        print(f"   ✓ Found {len(property_cols)} properties")
        if excluded_cols:
            print(f"   ℹ️  Excluded {len(excluded_cols)} columns")
        if binary_encodings:
            print(f"   ℹ️  Encoded {len(binary_encodings)} binary columns")
        print()
        
        # Use the encoded dataframe for subsequent analysis
        entities_df = entities_encoded
        
        # Apply binary encodings
        entities_encoded = entities_df.copy()
        for col, encoding_map in binary_encodings.items():
            entities_encoded[col] = entities_df[col].map(encoding_map)
        
        # Convert boolean columns to int (0/1) for correlations
        for col in property_cols:
            if pd.api.types.is_bool_dtype(entities_encoded[col]):
                entities_encoded[col] = entities_encoded[col].astype(int)
        
        # Step 6: Compute correlations
        print("🔗 Step 6: Computing correlations...")
        correlations = self.corr_analyzer.analyze(entities_encoded)
        
        # Format correlations for consistency with analyze
        for name, corr_data in correlations.items():
            # Rename value to r_value and round to 2 decimals
            if 'value' in corr_data:
                corr_data['r_value'] = round(corr_data['value'], 2)
                del corr_data['value']
            # Round p_value to 3 decimals
            if 'p_value' in corr_data:
                corr_data['p_value'] = round(corr_data['p_value'], 3)
        
        print(f"   ✓ Computed {len(correlations)} correlations\n")
        
        # Step 7: Build results
        print("📦 Step 7: Building results...")
        results = self._build_results(entities_df, statistics, correlations, property_cols, excluded_cols, binary_encodings, metrics_config)
        print("   ✓ Results compiled\n")
        
        print(f"{'='*100}")
        print("✨ Analysis complete!")
        print(f"{'='*100}\n")
        
        return results
    
    def _load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Dict[str, Any]]]:
        """
        Load entities CSV and metrics configuration.

        Returns:
            Tuple of (entities_df, metrics_df, metrics_config)
        """
        # Load entities from CSV
        print(f"   Loading entities CSV: {self.entities_csv}")

        if not self.entities_csv.exists():
            raise FileNotFoundError(f"CSV file not found: {self.entities_csv}")

        entities_df = pd.read_csv(self.entities_csv)

        # Convert column names to lowercase for consistency
        entities_df.columns = entities_df.columns.str.lower()

        # Load metrics configuration from YAML
        print(f"   Loading metrics config: {self.metrics_config}")
        metrics_config = self._load_metrics_config()
        print(f"      Found metrics: {', '.join(metrics_config.keys())}")

        # Compute metrics from entity data
        print(f"   Computing metrics from entity data...")
        metrics_df = self._compute_metrics(entities_df, metrics_config)

        return entities_df, metrics_df, metrics_config
    
    def _load_metrics_config(self) -> Dict[str, Dict[str, Any]]:
        """
        Load metrics configuration from YAML file.
        
        Returns:
            Dictionary mapping metric_name -> config
            Example: {
                'agent_install_rate': {
                    'source': 'installed_agent',
                    'type': 'rate',
                    'description': 'Agent installation rate'
                }
            }
        """
        config = yaml.safe_load(self.metrics_config.read_text())
        
        # Validate structure
        if 'metrics' not in config:
            raise ValueError("Metrics config must have 'metrics' key")
        
        # Validate each metric
        for metric_name, metric_def in config['metrics'].items():
            if 'source' not in metric_def:
                raise ValueError(f"Metric '{metric_name}' missing 'source' field")
            if 'type' not in metric_def:
                raise ValueError(f"Metric '{metric_name}' missing 'type' field")
            if metric_def['type'] not in ['rate', 'mean', 'sum', 'count']:
                raise ValueError(f"Metric '{metric_name}' has invalid type: {metric_def['type']}")
        
        return config['metrics']
    
    def _compute_metrics(
        self,
        entities_df: pd.DataFrame,
        metrics_config: Dict[str, Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Compute metrics from entity data using configuration.
        
        Args:
            entities_df: Entity-level data with 'variant' column
            metrics_config: Metrics configuration from YAML
        
        Returns:
            DataFrame with columns: variant, sample_size, metric1, metric2, ...
        """
        results = []
        
        for variant in ['blue', 'green']:
            variant_df = entities_df[entities_df['variant'] == variant]
            row = {
                'variant': variant,
                'sample_size': len(variant_df)
            }
            
            # Compute each metric
            for metric_name, metric_def in metrics_config.items():
                source_col = metric_def['source']
                metric_type = metric_def['type']
                
                # Validate source column exists
                if source_col not in entities_df.columns:
                    raise ValueError(f"Source column '{source_col}' not found in entities data")
                
                # Get data (handle per-metric NULL exclusion)
                data = variant_df[source_col].dropna()
                
                # Compute based on type
                if metric_type == 'rate':
                    # For binary: convert to numeric if needed, then sum/count
                    if pd.api.types.is_numeric_dtype(data):
                        row[metric_name] = data.sum() / len(data) if len(data) > 0 else 0.0
                    elif pd.api.types.is_bool_dtype(data):
                        row[metric_name] = data.sum() / len(data) if len(data) > 0 else 0.0
                    else:
                        # String binary column - find "truthy" values
                        # Count unique values to determine what's positive
                        unique_vals = sorted(data.unique())
                        if len(unique_vals) <= 2:
                            # Assume second value alphabetically is "positive" (e.g., 'yes' > 'no')
                            positive_val = unique_vals[-1] if len(unique_vals) > 1 else unique_vals[0]
                            success_count = (data == positive_val).sum()
                            row[metric_name] = success_count / len(data) if len(data) > 0 else 0.0
                        else:
                            raise ValueError(f"Rate metric '{metric_name}' has >2 unique values in source '{source_col}'")
                elif metric_type == 'mean':
                    row[metric_name] = data.mean() if len(data) > 0 else 0.0
                elif metric_type == 'sum':
                    row[metric_name] = data.sum()
                elif metric_type == 'count':
                    row[metric_name] = len(data)
            
            results.append(row)
        
        return pd.DataFrame(results)
    
    def _validate_data(self, entities_df: pd.DataFrame, metrics_df: pd.DataFrame):
        """Validate that data has required structure."""
        # Check entities has 'variant' column
        if 'variant' not in entities_df.columns:
            raise ValueError("Entities query must include 'variant' column")
        
        # Check variant values are 'blue' and 'green'
        variants = set(entities_df['variant'].unique())
        expected = {'blue', 'green'}
        if not variants.issubset(expected):
            raise ValueError(f"Variant must be 'blue' or 'green', got: {variants}")
        
        # Check metrics has 'variant' column
        if 'variant' not in metrics_df.columns:
            raise ValueError("Metrics query must include 'variant' column")
    
    def _handle_nulls(self, entities_df: pd.DataFrame) -> pd.DataFrame:
        """Handle NULL values based on strategy."""
        if self.null_handling == "error":
            if entities_df.isnull().any().any():
                null_cols = entities_df.columns[entities_df.isnull().any()].tolist()
                raise ValueError(f"NULL values found in columns: {null_cols}")
        
        elif self.null_handling == "per-entity":
            # Drop entire rows with any NULL
            entities_df = entities_df.dropna()
        
        # per-metric: handled during analysis (default)
        return entities_df
    
    def _identify_properties(self, df: pd.DataFrame) -> Tuple[List[str], List[str], Dict[str, Dict[str, int]], pd.DataFrame]:
        """
        Identify property columns, excluding IDs, timestamps, and columns with NULLs.
        Also encode binary string columns.
        
        Returns:
            Tuple of (property_cols, excluded_cols, binary_encodings, encoded_df)
        """
        property_cols = []
        excluded_cols = []
        binary_encodings = {}
        encoded_df = df.copy()
        
        for col in df.columns:
            # Skip org_id only (variant is a valid property)
            if col == 'org_id':
                continue
            
            col_lower = col.lower()
            
            # Skip ID columns
            if col_lower.endswith('_id') or col_lower.startswith('id_'):
                excluded_cols.append(f"{col} # ID column")
                continue
            
            # Skip timestamp/date columns
            if 'timestamp' in col_lower or 'date' in col_lower:
                excluded_cols.append(f"{col} # timestamp/date")
                continue
            
            # Skip columns with NULL values
            if df[col].isnull().any():
                null_count = df[col].isnull().sum()
                excluded_cols.append(f"{col} # contains {null_count} NULL values")
                continue
            
            # Check if boolean (track original labels)
            if pd.api.types.is_bool_dtype(df[col]):
                property_cols.append(col)
                # Convert to 0/1 and track encoding
                encoding_map = {False: 0, True: 1}
                encoded_df[col] = df[col].astype(int)
                binary_encodings[col] = {'False': 0, 'True': 1}
                continue
            
            # Check if numeric
            if pd.api.types.is_numeric_dtype(df[col]):
                property_cols.append(col)
                continue
            
            # Check if binary (≤2 unique non-null values)
            unique_vals = df[col].dropna().unique()
            if len(unique_vals) <= 2:
                property_cols.append(col)
                # Encode string/categorical binary columns as 0/1
                if not pd.api.types.is_numeric_dtype(df[col]):
                    sorted_vals = sorted(unique_vals.tolist())
                    encoding_map = {sorted_vals[i]: i for i in range(len(sorted_vals))}
                    # Store the encoding for metadata
                    binary_encodings[col] = {str(v): i for v, i in encoding_map.items()}
                continue
            
            # Exclude categorical with >2 values
            excluded_cols.append(f"{col} # categorical with {len(unique_vals)} values")
        
        return property_cols, excluded_cols, binary_encodings, encoded_df
    
    def _get_sample_values_str(self, series: pd.Series, n_samples: int = 3) -> str:
        """Get unique sample values from a series."""
        unique_vals = series.dropna().unique()
        sample_size = min(n_samples, len(unique_vals))
        sample_vals = pd.Series(unique_vals).sample(n=sample_size, random_state=42).tolist()
        
        # Format based on type
        if pd.api.types.is_integer_dtype(series):
            samples_str = ', '.join(str(int(v)) for v in sample_vals)
        elif pd.api.types.is_float_dtype(series):
            samples_str = ', '.join(f'{v:.2f}' for v in sample_vals)
        elif pd.api.types.is_bool_dtype(series):
            samples_str = ', '.join(str(v) for v in sample_vals)
        else:
            samples_str = ', '.join(str(v) for v in sample_vals)
        
        # Add ellipsis if there are more unique values
        if len(unique_vals) > len(sample_vals):
            samples_str += '...'
        
        return samples_str
    
    def _get_binary_encoding_str(self, encoding_map: Dict[str, int]) -> str:
        """Format binary encoding map into a string like 'key1 -> value1, key2 -> value2'."""
        pairs = [f"{k} -> {v}" for k, v in encoding_map.items()]
        return ', '.join(pairs)
    
    def _build_results(
        self,
        entities_df: pd.DataFrame,
        statistics: Dict[str, Any],
        correlations: Dict[str, Any],
        property_cols: List[str],
        excluded_cols: List[str],
        binary_encodings: Dict[str, Dict[str, int]],
        metrics_config: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build final results dictionary."""
        # Count sample sizes
        variant_counts = entities_df['variant'].value_counts()
        n_blue = int(variant_counts.get('blue', 0))
        n_green = int(variant_counts.get('green', 0))
        
        # Build properties list with sample values
        properties_with_samples = []
        for col in property_cols:
            # Check if this column has a binary encoding
            if col in binary_encodings:
                samples_str = self._get_binary_encoding_str(binary_encodings[col])
            else:
                samples_str = self._get_sample_values_str(entities_df[col])
            
            properties_with_samples.append(f"{col} # values: {samples_str}")
        
        return {
            'metadata': {
                'entities_csv': str(self.entities_csv),
                'metrics_config': str(self.metrics_config),
                'metrics_definitions': metrics_config,
                'n_blue': n_blue,
                'n_green': n_green,
                'properties': properties_with_samples,
                'excluded_columns': excluded_cols,
                'binary_encodings': binary_encodings,
                'null_handling': self.null_handling,
                'confidence_level': self.confidence_level
            },
            'metrics': statistics,
            'correlations': correlations
        }
    
    def to_yaml(self, results: Dict[str, Any]) -> str:
        """Convert results to YAML string."""
        yaml_output = yaml.dump(
            results,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True
        )
        
        # Post-process: Remove quotes from lines with " # values:" or " # "
        # and from binary_encodings keys (except YAML reserved words)
        # YAML requires quotes for # in strings and for reserved words, but we want clean output
        yaml_reserved = {'yes', 'no', 'true', 'false', 'on', 'off', 'y', 'n'}
        lines = []
        for line in yaml_output.split('\n'):
            # Match lines like "  - 'feature_name # values: x, y, z'" or "  - 'column # reason'"
            if ' # ' in line and (line.strip().startswith("- '") or line.strip().startswith('- "')):
                # Remove quotes while preserving indentation and dash
                indent = len(line) - len(line.lstrip())
                content = line.strip()[2:].strip()  # Remove "- " prefix
                # Remove surrounding quotes
                if content.startswith("'") and content.endswith("'"):
                    content = content[1:-1]
                elif content.startswith('"') and content.endswith('"'):
                    content = content[1:-1]
                line = ' ' * indent + '- ' + content
            # Remove quotes from binary_encodings keys (except reserved words)
            elif ':' in line and (line.strip().startswith("'") or line.strip().startswith('"')):
                # Match pattern like "      'no': 0" or '      "yes": 1'
                stripped = line.lstrip()
                if stripped[0] in ["'", '"']:
                    quote = stripped[0]
                    if quote in stripped[1:]:
                        end_quote_idx = stripped.index(quote, 1)
                        if end_quote_idx > 0 and stripped[end_quote_idx + 1:].startswith(':'):
                            key = stripped[1:end_quote_idx]
                            # Only remove quotes if NOT a YAML reserved word
                            if key.lower() not in yaml_reserved:
                                indent = len(line) - len(stripped)
                                rest = stripped[end_quote_idx + 1:]
                                line = ' ' * indent + key + rest
            lines.append(line)
        
        return '\n'.join(lines)


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Compare experiment variants with statistical significance testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic A/B test comparison
  %(prog)s --entities experiment.csv --metrics metrics.yaml

  # With custom output location
  %(prog)s --entities experiment.csv --metrics metrics.yaml --output results.yaml

  # With strict NULL handling (fail on any NULL)
  %(prog)s --entities experiment.csv --metrics metrics.yaml --null error

  # With 99%% confidence intervals
  %(prog)s --entities experiment.csv --metrics metrics.yaml --confidence 0.99

Input Requirements:

  Entities CSV must include:
    - variant column with values: 'blue' or 'green'
    - Entity identifier (e.g., org_id, user_id)
    - Properties to analyze (numeric or binary features)

  Example CSV:
    org_id,variant,installed_agent,revenue,signup_method
    1001,blue,true,1500,standard
    1002,green,false,0,trial
    1003,blue,true,2300,standard

  Metrics YAML defines how to compute metrics:
    metrics:
      agent_install_rate:
        source: installed_agent
        type: rate
        description: Agent installation rate
      avg_revenue:
        source: revenue
        type: mean
        description: Average revenue per org

  Supported metric types: rate, mean, sum, count

Output:
  YAML file with:
    - Statistical tests (t-tests, chi-square, Fisher's exact)
    - Effect sizes (Cohen's d, relative lift, confidence intervals)
    - P-values and significance indicators
    - Property correlations with visual bars

NULL Handling Strategies:
  per-metric  - Exclude NULLs per metric (default, maximizes data usage)
  per-entity  - Exclude entire rows with any NULLs (consistent sample)
  error       - Fail if any NULLs found (enforce data quality)
        """
    )

    parser.add_argument('--entities', required=True,
                        help='Path to entities CSV file (must include variant column)')
    parser.add_argument('--metrics', required=True,
                        help='Path to metrics YAML configuration')
    parser.add_argument('--output', default=None,
                        help='Output YAML file path (default: output.yaml next to entities CSV)')
    parser.add_argument('--null', dest='null_handling',
                        choices=['per-metric', 'per-entity', 'error'],
                        default='per-metric',
                        help='NULL handling strategy (default: per-metric)')
    parser.add_argument('--confidence', type=float, default=0.95,
                        help='Confidence level for intervals, e.g., 0.95 for 95%% CI (default: 0.95)')

    args = parser.parse_args()

    try:
        # Run comparison
        comparison = ExperimentComparison(
            entities_csv=args.entities,
            metrics_config=args.metrics,
            null_handling=args.null_handling,
            confidence_level=args.confidence
        )

        results = comparison.run()

        # Format output (always YAML)
        output = comparison.to_yaml(results)

        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            # Default: output.yaml next to entities CSV file
            entities_path = Path(args.entities)
            output_path = entities_path.parent / 'output.yaml'
        
        # Save to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)
        print(f"✓ Results saved to: {output_path}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

