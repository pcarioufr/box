#!/usr/bin/env python3
"""
Exploratory Data Analysis - Pattern Discovery

Discovers patterns in entity-level data through clustering and correlation analysis.

Usage:
    ./box.sh analysis analyze --entities entities.csv [options]
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import yaml

# Import statistical utilities
from .stats.clustering import ClusterAnalyzer
from .stats.correlations import CorrelationAnalyzer


class ExploratoryAnalysis:
    """
    High-level orchestrator for exploratory data analysis.
    
    Coordinates the analysis pipeline:
    1. Execute SQL query (via libs/snowflake/query.py)
    2. Identify numeric/binary features
    3. Perform clustering (k-means)
    4. Compute correlations (all pairs)
    5. Analyze by variant (if present)
    6. Generate output
    """
    
    def __init__(
        self,
        entities_csv: str,
        n_clusters: int = None,
        debug: bool = False,
        sampling: int = None
    ):
        """
        Initialize the analysis.

        Args:
            entities_csv: Path to entities CSV file
            n_clusters: Number of clusters (None = auto-detect)
            debug: If True, include detailed statistics in output and print to stdout
            sampling: Sample rate for optimal k search (e.g., 2=half, 10=1/10th of data)
        """
        self.entities_csv = Path(entities_csv)
        self.n_clusters = n_clusters
        self.debug = debug
        self.sampling = sampling

        # Initialize analyzers
        self.cluster_analyzer = ClusterAnalyzer()
        self.corr_analyzer = CorrelationAnalyzer()
        
    def run(self) -> Dict[str, Any]:
        """
        Run the complete analysis pipeline.
        
        Returns:
            Analysis results dictionary
        """
        print(f"\n{'='*100}")
        print("EXPLORATORY DATA ANALYSIS")
        print(f"{'='*100}\n")
        
        # Step 1: Load CSV data
        print("📊 Step 1: Loading CSV data...")
        entities_df = self._load_csv()
        print(f"   ✓ Entities loaded: {len(entities_df)} rows\n")
        
        # Step 2: Identify features
        print("🔍 Step 2: Identifying features...")
        feature_cols, encoded_df, feature_metadata = self._identify_features(entities_df)
        print(f"   ✓ Found {len(feature_cols)} features: {', '.join(feature_cols)}")
        if feature_metadata['excluded_columns']:
            print(f"   ℹ️  Excluded {len(feature_metadata['excluded_columns'])} columns")
        if feature_metadata['binary_encodings']:
            print(f"   ℹ️  Encoded {len(feature_metadata['binary_encodings'])} binary columns")
        print()
        
        if len(feature_cols) == 0:
            raise ValueError("No valid features found for analysis")
        
        # Step 3: Perform clustering (use encoded dataframe)
        print(f"🎯 Step 3: Performing clustering...")
        encoded_df = self.cluster_analyzer.cluster(
            encoded_df,
            feature_cols,
            n_clusters=self.n_clusters,
            sampling=self.sampling
        )
        clusters = self.cluster_analyzer.analyze_clusters(
            encoded_df, 
            feature_cols, 
            binary_encodings=feature_metadata['binary_encodings'],
            debug=self.debug
        )
        print(f"   ✓ Clusters identified\n")
        
        # Step 4: Compute correlations (use encoded dataframe)
        print("🔗 Step 4: Computing correlations...")
        correlations = self._compute_all_correlations(encoded_df, feature_cols)
        print(f"   ✓ Analyzed {len(correlations)} feature pairs\n")
        
        # Step 5: Build results
        print(f"📦 Step 5: Building results...")
        results = self._build_results(
            encoded_df,
            feature_cols,
            clusters,
            correlations,
            feature_metadata
        )
        print("   ✓ Results compiled\n")
        
        print(f"\n{'='*100}")
        print("✨ Analysis complete!")
        print(f"{'='*100}\n")
        
        return results
    
    def _load_csv(self) -> pd.DataFrame:
        """
        Load data from CSV file.

        Returns:
            DataFrame with entity data
        """
        print(f"   Loading: {self.entities_csv}")

        if not self.entities_csv.exists():
            raise FileNotFoundError(f"CSV file not found: {self.entities_csv}")

        df = pd.read_csv(self.entities_csv)

        # Convert column names to lowercase for consistency
        df.columns = df.columns.str.lower()

        return df
    
    def _identify_features(self, df: pd.DataFrame) -> tuple[List[str], pd.DataFrame, Dict[str, Any]]:
        """
        Identify numeric and binary features for analysis.
        
        Includes:
        - All numeric columns (int, float)
        - All binary columns (≤2 unique values, including strings)
        
        Excludes:
        - ID columns (ending with _id or starting with id_)
        - Timestamp/date columns
        - Categorical columns with >2 unique values
        
        Args:
            df: DataFrame with entity data
        
        Returns:
            Tuple of (feature_cols, encoded_df, metadata):
            - feature_cols: List of feature column names
            - encoded_df: DataFrame with binary strings encoded as 0/1
            - metadata: Dict with excluded_columns and binary_encodings
        """
        feature_cols = []
        excluded_cols = []
        binary_encodings = {}
        encoded_df = df.copy()
        
        for col in df.columns:
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
                feature_cols.append(col)
                # Convert to 0/1 and track encoding
                encoding_map = {False: 0, True: 1}
                encoded_df[col] = df[col].astype(int)
                binary_encodings[col] = {'False': 0, 'True': 1}
                continue
            
            # Check if numeric
            if pd.api.types.is_numeric_dtype(df[col]):
                feature_cols.append(col)
                continue
            
            # Check if binary (≤2 unique non-null values)
            unique_vals = df[col].dropna().unique()
            if len(unique_vals) <= 2:
                feature_cols.append(col)
                # Encode string/categorical binary columns as 0/1
                if not pd.api.types.is_numeric_dtype(df[col]):
                    sorted_vals = sorted(unique_vals.tolist())
                    encoding_map = {sorted_vals[i]: i for i in range(len(sorted_vals))}
                    encoded_df[col] = df[col].map(encoding_map)
                    # Store the encoding for metadata
                    binary_encodings[col] = {str(v): i for v, i in encoding_map.items()}
                continue
            
            # Exclude categorical with >2 values
            excluded_cols.append(f"{col} # categorical with {len(unique_vals)} values")
        
        metadata = {
            'excluded_columns': excluded_cols if excluded_cols else None,
            'binary_encodings': binary_encodings if binary_encodings else None
        }
        
        return feature_cols, encoded_df, metadata
    
    def _compute_all_correlations(
        self,
        df: pd.DataFrame,
        feature_cols: List[str]
    ) -> Dict[str, Any]:
        """
        Compute correlations between all feature pairs.
        
        Args:
            df: DataFrame with entity data
            feature_cols: List of feature column names
        
        Returns:
            Dictionary of correlation results keyed by feature pair names
        """
        all_corrs = self.corr_analyzer.analyze(df[feature_cols])
        
        # Enrich correlations with visual indicators
        total_entities = len(df)
        for name, corr_data in all_corrs.items():
            # Skip NaN correlations (constant variables)
            if pd.isna(corr_data['value']):
                continue
            enrichment = self._enrich_correlation(corr_data, total_entities)
            # Add visual_bar and non_null_pct to output
            corr_data['visual_bar'] = enrichment['visual_bar']
            corr_data['non_null_pct'] = f"{enrichment['non_null_pct']}%"
            # Rename value to r_value (keep as float for now, format later)
            corr_data['r_value'] = corr_data['value']
            del corr_data['value']
            del corr_data['n']
        
        # Format all numeric values for final output
        for name, corr_data in all_corrs.items():
            if 'r_value' in corr_data:
                # Round to preserve precision without converting to string
                corr_data['r_value'] = round(corr_data['r_value'], 2)
                corr_data['p_value'] = round(corr_data['p_value'], 3)
        
        return all_corrs
    
    def _enrich_correlation(self, corr_data: Dict[str, Any], total_entities: int) -> Dict[str, Any]:
        """
        Add visual indicators to correlation data.
        
        Args:
            corr_data: Correlation dictionary with 'value' and 'p_value'
            total_entities: Total number of entities in the dataset
        
        Returns:
            Dictionary with visual_bar and non_null_pct
        """
        value = corr_data['value']
        p_value = corr_data['p_value']
        n = corr_data['n']
        
        # Calculate non-null percentage
        non_null_pct = int(round(100 * n / total_entities))
        
        # Statistical significance
        if p_value < 0.001:
            sig_indicator = "***"
        elif p_value < 0.01:
            sig_indicator = "**"
        elif p_value < 0.05:
            sig_indicator = "*"
        else:
            sig_indicator = "ns"
        
        # ASCII bar chart (20 chars wide, centered at position 10)
        bar_length = int(abs(value) * 10)  # 0 to 10 blocks from center
        
        if value >= 0:
            # Positive: fills right from center with █
            left_empty = 10
            right_filled = bar_length
            right_empty = 10 - bar_length
            bar = "░" * left_empty + "█" * right_filled + "░" * right_empty
        else:
            # Negative: fills left from center with ▓
            left_empty = 10 - bar_length
            left_filled = bar_length
            right_empty = 10
            bar = "░" * left_empty + "▓" * left_filled + "░" * right_empty
        
        # Combine bar with significance indicator
        visual_bar = f"{bar} {sig_indicator}"
        
        return {
            'visual_bar': visual_bar,
            'non_null_pct': non_null_pct
        }
    
    def _build_results(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        clusters: Dict[str, Any],
        correlations: Dict[str, Any],
        feature_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build final results dictionary.
        
        Args:
            df: DataFrame analyzed
            feature_cols: List of feature columns
            clusters: Cluster analysis results
            correlations: Correlation analysis results
            feature_metadata: Metadata about features (excluded columns, encodings)
        
        Returns:
            Dictionary with analysis results
        """
        # Build features list with sample values
        features_with_samples = []
        for col in feature_cols:
            # Check if this column has a binary encoding
            if feature_metadata['binary_encodings'] and col in feature_metadata['binary_encodings']:
                # Show the encoding mapping
                encoding = feature_metadata['binary_encodings'][col]
                # Sort by value to show in order
                sorted_items = sorted(encoding.items(), key=lambda x: x[1])
                mapping_str = ', '.join(f"{k} -> {v}" for k, v in sorted_items)
                features_with_samples.append(f"{col} # values: {mapping_str}")
            else:
                # Get unique values, then sample from them
                unique_vals = df[col].dropna().unique()
                sample_size = min(3, len(unique_vals))
                sample_vals = pd.Series(unique_vals).sample(n=sample_size, random_state=42).tolist()
                
                # Format sample values based on type
                if df[col].dtype in ['int64', 'int32']:
                    samples_str = ', '.join(str(int(v)) for v in sample_vals)
                elif df[col].dtype in ['float64', 'float32']:
                    # Check if values look like binary (0.0, 1.0)
                    if set(unique_vals).issubset({0.0, 1.0}):
                        samples_str = ', '.join(str(int(v)) for v in sample_vals)
                    else:
                        samples_str = ', '.join(f'{v:.2f}' for v in sample_vals)
                else:
                    samples_str = ', '.join(str(v) for v in sample_vals)
                
                # Add ellipsis only if there are more unique values than shown
                if len(unique_vals) > len(sample_vals):
                    samples_str += '...'
                
                features_with_samples.append(f"{col} # values: {samples_str}")
        
        metadata = {
            'entities_csv': str(self.entities_csv),
            'n_entities': len(df),
            'features': features_with_samples
        }
        
        # Add excluded columns if any
        if feature_metadata['excluded_columns']:
            metadata['excluded_columns'] = feature_metadata['excluded_columns']
        
        # Add binary encodings if any
        if feature_metadata['binary_encodings']:
            metadata['binary_encodings'] = feature_metadata['binary_encodings']
        
        results = {
            'metadata': metadata,
            'clusters': clusters,
            'correlations': {name: corr for name, corr in correlations.items() 
                            if 'r_value' in corr}  # Only include correlations that were successfully computed
        }
        
        return results
    
    def to_yaml(self, results: Dict[str, Any]) -> str:
        """Convert results to YAML string."""
        # Disable anchors/aliases by using safe dump with custom representer
        class NoAliasDumper(yaml.SafeDumper):
            def ignore_aliases(self, data):
                return True
        
        yaml_output = yaml.dump(
            results,
            Dumper=NoAliasDumper,
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
        description="Exploratory data analysis: clustering and correlation discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect optimal number of clusters
  %(prog)s --entities customer_data.csv

  # Specify number of clusters
  %(prog)s --entities customer_data.csv --clusters 4

  # Use sampling for faster k-selection on large datasets (>10k rows)
  %(prog)s --entities customer_data.csv --sampling 10

  # With debug output showing detailed statistics
  %(prog)s --entities customer_data.csv --debug

  # Custom output location
  %(prog)s --entities customer_data.csv --output analysis_results.yaml

Input Requirements:

  Entities CSV with numeric or binary features:
    - Numeric columns (int, float) are included as-is
    - Binary columns (≤2 unique values) are auto-encoded as 0/1
    - Optional 'variant' column for variant-specific analysis

  Example CSV:
    org_id,installed_agent,signup_method,session_count,trial_days
    1001,yes,standard,15,30
    1002,no,trial,2,7
    1003,yes,standard,23,30

  Automatically excluded:
    - ID columns (ending with _id)
    - Timestamp/date columns
    - Categorical columns with >2 unique values
    - Columns with NULL values

Output:
  YAML file with:
    - Cluster profiles (size, percentage, feature distributions)
    - Feature correlations (all pairs, with p-values)
    - Visual distribution bars for each cluster
    - Binary encoding mappings for reference

Clustering:
  Uses k-means with silhouette score for automatic k selection.
  Default range: k=2 to k=10
  Sampling accelerates k-selection on large datasets without affecting final clustering.

Feature Auto-encoding:
  Binary strings are encoded as 0/1 alphabetically:
    "no" -> 0, "yes" -> 1
    "false" -> 0, "true" -> 1
    "standard" -> 0, "trial" -> 1
        """
    )

    parser.add_argument('--entities', required=True,
                        help='Path to entities CSV file with numeric/binary features')
    parser.add_argument('--output', default=None,
                        help='Output YAML file path (default: output.yaml next to entities CSV)')
    parser.add_argument('--clusters', type=int, default=None,
                        help='Number of clusters (default: auto-detect using silhouette method)')
    parser.add_argument('--sampling', type=int, default=None,
                        help='Sample rate for k-selection (e.g., 10 = use 1/10th of data). Speeds up k-selection on large datasets.')
    parser.add_argument('--debug', action='store_true',
                        help='Include detailed cluster statistics in output and print to stdout')

    args = parser.parse_args()

    try:
        # Run analysis
        analysis = ExploratoryAnalysis(
            entities_csv=args.entities,
            n_clusters=args.clusters,
            debug=args.debug,
            sampling=args.sampling
        )

        results = analysis.run()

        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            # Default: output.yaml next to entities CSV file
            entities_path = Path(args.entities)
            output_path = entities_path.parent / 'output.yaml'
        
        # Save to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_output = analysis.to_yaml(results)
        output_path.write_text(yaml_output)
        print(f"✓ Analysis results written to: {output_path}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

