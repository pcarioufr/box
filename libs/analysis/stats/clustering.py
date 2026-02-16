"""
Clustering Analysis

K-means and hierarchical clustering for exploratory data analysis.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, calinski_harabasz_score


class ClusterAnalyzer:
    """
    Performs clustering analysis on entity-level data.
    
    Methods:
    - find_optimal_k: Determines optimal number of clusters using elbow method
    - cluster: Performs k-means clustering
    - analyze_clusters: Characterizes each cluster
    """
    
    def __init__(self, random_state: int = 42):
        """
        Initialize cluster analyzer.
        
        Args:
            random_state: Random seed for reproducibility
        """
        self.random_state = random_state
        self.scaler = StandardScaler()
    
    def _generate_distribution_bar(
        self,
        cluster_min: float,
        cluster_max: float,
        cluster_mean: float,
        cluster_std: float,
        global_min: float,
        global_max: float,
        bar_width: int = 20
    ) -> str:
        """
        Generate a visual distribution bar for a cluster feature.
        
        Format: <gmin> _░░░░▓▓▓▓▓░░░░░___ <gmax>
        - _ = outside cluster range
        - ░ = within cluster range (min to max)
        - ▓ = within mean ± std (clamped to cluster range)
        
        Args:
            cluster_min: Minimum value in cluster
            cluster_max: Maximum value in cluster
            cluster_mean: Mean value in cluster
            cluster_std: Standard deviation in cluster
            global_min: Minimum value across all clusters
            global_max: Maximum value across all clusters
            bar_width: Width of the bar in characters
        
        Returns:
            Visual distribution string
        """
        # Handle edge case where global_min == global_max
        if global_max == global_min:
            return f"{global_min:.2f} ▓{'▓' * (bar_width - 2)}▓ {global_max:.2f}"
        
        # Normalize to 0-1 range
        def normalize(val):
            return (val - global_min) / (global_max - global_min)
        
        # Convert to bar positions (0 to bar_width-1)
        def to_pos(val):
            return int(normalize(val) * (bar_width - 1))
        
        cluster_min_pos = to_pos(cluster_min)
        cluster_max_pos = to_pos(cluster_max)
        
        # Mean ± std range (clamped to cluster min/max)
        mean_std_min = max(cluster_min, cluster_mean - cluster_std)
        mean_std_max = min(cluster_max, cluster_mean + cluster_std)
        mean_std_min_pos = to_pos(mean_std_min)
        mean_std_max_pos = to_pos(mean_std_max)
        
        # Build the bar
        bar = []
        for i in range(bar_width):
            if i < cluster_min_pos or i > cluster_max_pos:
                bar.append('_')  # Outside cluster range
            elif i >= mean_std_min_pos and i <= mean_std_max_pos:
                bar.append('▓')  # Within mean ± std
            else:
                bar.append('░')  # Within cluster range but outside mean ± std
        
        return f"{global_min:.2f} {''.join(bar)} {global_max:.2f}"
    
    def find_optimal_k(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        min_k: int = 2,
        max_k: int = 10,
        sampling: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Find optimal number of clusters using elbow method and silhouette score.
        
        Args:
            df: DataFrame with entity data
            feature_cols: List of feature column names
            min_k: Minimum number of clusters to try
            max_k: Maximum number of clusters to try
            sampling: Sample rate (e.g., 2=half, 10=1/10th of data). If provided, uses sample for k selection.
        
        Returns:
            Dictionary with optimal k and evaluation metrics
        """
        # Apply sampling if requested
        df_for_k = df
        if sampling is not None and sampling > 1:
            sample_size = max(len(df) // sampling, max_k * 2)  # Ensure at least 2× max_k
            if sample_size >= len(df):
                # Sample would be same size or larger, skip sampling
                print(f"   ⚠️  Dataset too small ({len(df):,} entities) for sampling rate {sampling}, using full dataset")
            else:
                print(f"   ⚠️  Using sampling: {sample_size:,} entities (1/{sampling} of {len(df):,}) for optimal k selection")
                df_for_k = df.sample(n=sample_size, random_state=42)
        
        print(f"   Finding optimal number of clusters (k={min_k} to {max_k})...")
        
        # Prepare features
        X = df_for_k[feature_cols].values
        X_scaled = self.scaler.fit_transform(X)
        
        # Try different k values
        inertias = []
        silhouette_scores = []
        calinski_scores = []
        
        total_k = max_k - min_k + 1
        for idx, k in enumerate(range(min_k, max_k + 1), 1):
            print(f"      Testing k={k} ({idx}/{total_k})...", end='\r')
            kmeans = KMeans(n_clusters=k, random_state=self.random_state, n_init=10)
            labels = kmeans.fit_predict(X_scaled)
            
            inertias.append(kmeans.inertia_)
            silhouette_scores.append(silhouette_score(X_scaled, labels))
            calinski_scores.append(calinski_harabasz_score(X_scaled, labels))
        
        print()  # Clear progress line
        
        # Find optimal k (highest silhouette score)
        optimal_idx = np.argmax(silhouette_scores)
        optimal_k = min_k + optimal_idx
        
        print(f"      Optimal k: {optimal_k} (silhouette: {silhouette_scores[optimal_idx]:.3f})")
        
        return {
            'optimal_k': optimal_k,
            'silhouette_score': silhouette_scores[optimal_idx],
            'calinski_harabasz_score': calinski_scores[optimal_idx],
            'evaluation': {
                'k_values': list(range(min_k, max_k + 1)),
                'inertias': inertias,
                'silhouette_scores': silhouette_scores,
                'calinski_harabasz_scores': calinski_scores
            }
        }
    
    def cluster(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        n_clusters: Optional[int] = None,
        sampling: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Perform k-means clustering.
        
        Args:
            df: DataFrame with entity data
            feature_cols: List of feature column names
            n_clusters: Number of clusters (if None, finds optimal)
            sampling: Sample rate for optimal k search (e.g., 2=half, 10=1/10th of data)
        
        Returns:
            DataFrame with added 'cluster' column
        """
        # Prepare features
        X = df[feature_cols].values
        X_scaled = self.scaler.fit_transform(X)
        
        # Determine number of clusters
        if n_clusters is None:
            optimal = self.find_optimal_k(df, feature_cols, sampling=sampling)
            n_clusters = optimal['optimal_k']
        else:
            print(f"   Using k={n_clusters} clusters...")
        
        # Perform clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=self.random_state, n_init=10)
        df['cluster'] = kmeans.fit_predict(X_scaled)
        
        # Store cluster centers (in original scale)
        self.cluster_centers_ = kmeans.cluster_centers_
        self.feature_cols_ = feature_cols
        
        return df
    
    def analyze_clusters(
        self, 
        df: pd.DataFrame, 
        feature_cols: List[str], 
        binary_encodings: Dict[str, Dict[str, int]] = None,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze characteristics of each cluster.
        
        Args:
            df: DataFrame with 'cluster' column
            feature_cols: List of feature column names
            binary_encodings: Dict mapping column names to their label->value encodings
            debug: If True, include detailed statistics in output and print to stdout
        
        Returns:
            Dictionary with cluster characteristics
        """
        if 'cluster' not in df.columns:
            raise ValueError("DataFrame must have 'cluster' column. Run cluster() first.")
        
        if binary_encodings is None:
            binary_encodings = {}
        
        print(f"   Analyzing {df['cluster'].nunique()} clusters...")
        
        # First pass: compute global min/max for each feature
        global_stats = {}
        for col in feature_cols:
            global_stats[col] = {
                'min': float(df[col].min()),
                'max': float(df[col].max())
            }
        
        clusters = {}
        
        for cluster_id in sorted(df['cluster'].unique()):
            cluster_df = df[df['cluster'] == cluster_id]
            
            # Compute statistics for each feature
            feature_stats = {}
            for col in feature_cols:
                cluster_mean = float(cluster_df[col].mean())
                cluster_std = float(cluster_df[col].std())
                cluster_min = float(cluster_df[col].min())
                cluster_max = float(cluster_df[col].max())
                
                # Check if this is a binary feature with encoding
                if col in binary_encodings:
                    # Use original labels instead of 0.00/1.00
                    encoding = binary_encodings[col]
                    # Reverse the encoding to get value->label mapping
                    reverse_encoding = {v: k for k, v in encoding.items()}
                    
                    # Get labels for min and max
                    global_min_val = int(global_stats[col]['min'])
                    global_max_val = int(global_stats[col]['max'])
                    min_label = reverse_encoding.get(global_min_val, str(global_min_val))
                    max_label = reverse_encoding.get(global_max_val, str(global_max_val))
                    
                    # Generate visual distribution bar
                    visual_bar = self._generate_distribution_bar(
                        cluster_min, cluster_max, cluster_mean, cluster_std,
                        global_stats[col]['min'], global_stats[col]['max']
                    )
                    
                    # Replace numeric labels with original labels  
                    # The bar format is "min_val bar max_val"
                    parts = visual_bar.split(' ')
                    if len(parts) >= 3:
                        parts[0] = min_label  # Replace first part (min value)
                        parts[-1] = max_label  # Replace last part (max value)
                        visual_bar = ' '.join(parts)
                else:
                    # Generate visual distribution bar with numeric labels
                    visual_bar = self._generate_distribution_bar(
                        cluster_min, cluster_max, cluster_mean, cluster_std,
                        global_stats[col]['min'], global_stats[col]['max']
                    )
                
                # Debug output: print detailed stats
                if debug:
                    print(f"         {col}: mean={cluster_mean:.3f}, std={cluster_std:.3f}, min={cluster_min:.1f}, max={cluster_max:.1f}")
                    print(f"           {visual_bar}")
                
                # Store only distribution bar by default, full stats if debug
                if debug:
                    feature_stats[col] = {
                        'mean': cluster_mean,
                        'std': cluster_std,
                        'min': cluster_min,
                        'max': cluster_max,
                        'distribution': visual_bar
                    }
                else:
                    feature_stats[col] = visual_bar
            
            # Characterize cluster based on highest/lowest features
            if debug:
                means = {col: feature_stats[col]['mean'] for col in feature_cols}
            else:
                means = {col: float(cluster_df[col].mean()) for col in feature_cols}
            
            overall_means = {col: float(df[col].mean()) for col in feature_cols}
            
            # Find distinctive features (>20% different from overall mean)
            high_features = []
            low_features = []
            for col in feature_cols:
                diff = means[col] - overall_means[col]
                rel_diff = diff / (overall_means[col] + 1e-10)  # Avoid div by zero
                
                if abs(rel_diff) > 0.2:  # 20% threshold
                    if rel_diff > 0:
                        high_features.append(col)
                    else:
                        low_features.append(col)
            
            # Generate description
            description_parts = []
            if high_features:
                description_parts.append(f"High: {', '.join(high_features)}")
            if low_features:
                description_parts.append(f"Low: {', '.join(low_features)}")
            
            description = "; ".join(description_parts) if description_parts else "Average across all features"
            
            cluster_data = {
                'percentage': round(float(len(cluster_df) / len(df) * 100)),
                'features': feature_stats
            }
            
            # Only include centroid in debug mode (redundant otherwise)
            if debug:
                cluster_data['centroid'] = means
            
            clusters[f'cluster_{cluster_id}'] = cluster_data
            
            print(f"      Cluster {cluster_id}: n={len(cluster_df)} ({len(cluster_df)/len(df)*100:.1f}%) - {description}")
        
        return clusters
    
    def analyze_by_variant(
        self,
        df: pd.DataFrame,
        variant_col: str = 'variant'
    ) -> Dict[str, Any]:
        """
        Analyze cluster distribution across variants.
        
        Args:
            df: DataFrame with 'cluster' and variant columns
            variant_col: Name of variant column
        
        Returns:
            Dictionary with variant-specific cluster distributions
        """
        if 'cluster' not in df.columns:
            raise ValueError("DataFrame must have 'cluster' column. Run cluster() first.")
        
        if variant_col not in df.columns:
            return {}
        
        print(f"   Analyzing cluster distribution by {variant_col}...")
        
        variants = {}
        
        for variant in sorted(df[variant_col].unique()):
            variant_df = df[df[variant_col] == variant]
            cluster_dist = variant_df['cluster'].value_counts(normalize=True).sort_index()
            
            variants[str(variant)] = {
                'size': int(len(variant_df)),
                'cluster_distribution': {
                    f'cluster_{int(k)}': float(v) for k, v in cluster_dist.items()
                }
            }
        
        # Chi-square test for independence
        try:
            from scipy.stats import chi2_contingency
            
            contingency = pd.crosstab(df[variant_col], df['cluster'])
            chi2, p_value, dof, expected = chi2_contingency(contingency)
            
            variants['statistical_test'] = {
                'test': 'chi_square',
                'chi2': float(chi2),
                'p_value': float(p_value),
                'degrees_of_freedom': int(dof),
                'significant': bool(p_value < 0.05)
            }
            
            print(f"      Chi-square test: p={p_value:.4f} ({'significant' if p_value < 0.05 else 'not significant'})")
        
        except Exception as e:
            print(f"      Warning: Could not perform chi-square test: {e}")
        
        return variants

