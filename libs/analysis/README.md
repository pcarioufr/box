# Analysis Library

Statistical analysis workflows for tabular data (CSV files).

## Overview

This library provides two main analytical workflows:
- **compare** - A/B test comparison with statistical significance testing
- **analyze** - Exploratory data analysis with clustering and correlations

Both workflows operate on CSV files and produce YAML output with detailed statistical results.

## Quick Start

```bash
# A/B test comparison
./box.sh analysis compare --entities entities.csv --metrics metrics.yaml

# Exploratory analysis
./box.sh analysis analyze --entities entities.csv
./box.sh analysis analyze --entities entities.csv --clusters 3
```

---

## Commands

### `compare` - A/B Test Comparison

Compare two experiment variants (blue vs green) with statistical significance testing.

**Usage:**
```bash
./box.sh analysis compare --entities <csv-file> --metrics <yaml-file> [options]
```

**Options:**
- `--entities <path>` - Path to entities CSV file (required)
- `--metrics <path>` - Path to metrics YAML configuration (required)
- `--output <path>` - Output file path (default: `output.yaml` next to entities CSV)
- `--null <strategy>` - NULL handling: `per-metric` (default), `per-entity`, `error`
- `--confidence <level>` - Confidence level for intervals (default: 0.95)

**Input Requirements:**

**Entities CSV:**
- Must include `variant` column with values: `blue`, `green`
- Must include entity identifier (e.g., `org_id`)
- Can include any number of additional properties
- Example:
  ```csv
  org_id,variant,installed_agent,datacenter,signup_method
  1001,blue,true,us1,standard
  1002,green,false,eu1,trial
  ```

**Metrics YAML:**
- Defines how to compute metrics from entity properties
- Supported metric types: `rate`, `mean`, `sum`, `count`
- Example:
  ```yaml
  metrics:
    agent_install_rate:
      source: installed_agent
      type: rate
      description: Agent installation rate

    avg_session_duration:
      source: session_duration_seconds
      type: mean
      description: Average session duration
  ```

**Output:**
- YAML file with metadata, metrics (with statistical tests), and correlations
- Includes sample sizes, confidence intervals, p-values
- Property correlations with visual bars and significance indicators

---

### `analyze` - Exploratory Data Analysis

Discover patterns in entity-level data through clustering and correlation analysis.

**Usage:**
```bash
./box.sh analysis analyze --entities <csv-file> [options]
```

**Options:**
- `--entities <path>` - Path to entities CSV file (required)
- `--output <path>` - Output file path (default: `output.yaml` next to entities CSV)
- `--clusters <n>` - Number of clusters (default: auto-detect using silhouette method)
- `--sampling <rate>` - Sample rate for optimal k search (e.g., 2=half, 10=1/10th)
- `--debug` - Include detailed statistics in output and print to stdout

**Input Requirements:**

**Entities CSV:**
- Can include any number of numeric or binary features
- Optional `variant` column for variant-specific analysis
- Features are auto-detected:
  - Numeric columns (int, float)
  - Binary columns (≤2 unique values, including strings)
- Example:
  ```csv
  org_id,installed_agent,datacenter,signup_method,session_count,trial_length_days
  1001,yes,us1,standard,15,30
  1002,no,eu1,trial,2,7
  ```

**Feature Detection:**
- **Included:** Numeric, binary (≤2 values), boolean
- **Excluded:** IDs (ends with `_id`), timestamps/dates, categoricals (>2 values), NULLs
- **Encoded:** Binary strings automatically encoded as 0/1 (e.g., "no"→0, "yes"→1)

**Output:**
- YAML file with metadata, clusters, and correlations
- Cluster sizes, means, and distributions
- Correlation matrix with visual bars and significance indicators
- Binary encoding mappings for reference

---

## Programmatic Usage

### Compare Workflow

```python
from libs.analysis import ExperimentComparison

# Initialize comparison
comparison = ExperimentComparison(
    entities_csv="entities.csv",
    metrics_config="metrics.yaml",
    null_handling="per-metric",
    confidence_level=0.95
)

# Run analysis
results = comparison.run()

# Access results
print(f"Blue sample size: {results['metadata']['n_blue']}")
print(f"Green sample size: {results['metadata']['n_green']}")

for metric_name, metric_data in results['metrics'].items():
    print(f"{metric_name}: {metric_data['test']}")
    print(f"  p-value: {metric_data['p_value']}")
    print(f"  significant: {metric_data['significant']}")

# Export to YAML
yaml_output = comparison.to_yaml(results)
Path("output.yaml").write_text(yaml_output)
```

### Analyze Workflow

```python
from libs.analysis import ExploratoryAnalysis

# Initialize analysis
analysis = ExploratoryAnalysis(
    entities_csv="entities.csv",
    n_clusters=None,  # Auto-detect
    debug=False,
    sampling=None
)

# Run analysis
results = analysis.run()

# Access results
print(f"Entities analyzed: {results['metadata']['n_entities']}")
print(f"Features: {results['metadata']['features']}")

for cluster_id, cluster_data in results['clusters'].items():
    print(f"{cluster_id}: {cluster_data['percentage']}% of entities")

# Export to YAML
yaml_output = analysis.to_yaml(results)
Path("output.yaml").write_text(yaml_output)
```

---

## Statistical Utilities

The library also exports low-level statistical utilities for custom workflows:

```python
# Import from top-level package
from libs.analysis import StatisticalAnalyzer, CorrelationAnalyzer, ClusterAnalyzer

# Or import directly from stats subpackage
from libs.analysis.stats import StatisticalAnalyzer, CorrelationAnalyzer, ClusterAnalyzer

# Statistical tests
analyzer = StatisticalAnalyzer(confidence_level=0.95)
result = analyzer.analyze_binary_metric(df, 'conversion', 'converted')

# Correlations
corr_analyzer = CorrelationAnalyzer()
correlations = corr_analyzer.analyze(df)

# Clustering
cluster_analyzer = ClusterAnalyzer()
df = cluster_analyzer.cluster(df, feature_cols=['x', 'y', 'z'], n_clusters=3)
clusters = cluster_analyzer.analyze_clusters(df, feature_cols)
```

See `guides/` directory for detailed guides on clustering and correlation interpretation.

---

## NULL Handling Strategies

The `compare` workflow supports three NULL handling strategies:

### `per-metric` (default)
- Each metric computation excludes NULLs only for its source column
- Different metrics may use different sample sizes
- **Use when:** Data quality varies by feature, want maximum data utilization

### `per-entity`
- Exclude entire entities (rows) that have ANY NULL values
- All metrics use the same sample size
- **Use when:** Need consistent entity set across all metrics

### `error`
- Fail if ANY NULL values are found
- Forces upstream data quality
- **Use when:** NULLs indicate data quality issues that must be resolved

---

## Architecture

```
libs/analysis/
├── compare.py         # A/B test comparison workflow (CLI entry point)
├── analyze.py         # Exploratory analysis workflow (CLI entry point)
├── stats/             # Statistical utilities (building blocks)
│   ├── statistics.py  # Hypothesis testing (t-tests, chi-square, effect sizes)
│   ├── correlations.py # Correlation analysis (phi coefficient, point-biserial)
│   └── clustering.py  # K-means clustering with silhouette optimization
└── guides/            # Detailed interpretation guides
    ├── CLUSTERING_GUIDE.md
    └── CORRELATION_GUIDE.md
```

**Design Principle:**
- **Workflows** (compare, analyze) - High-level orchestration, CLI entry points
- **Stats utilities** (stats/) - Low-level building blocks, reusable functions
- CSV-first: Simple data loading with `pd.read_csv()`
- All inputs/outputs use standard formats (CSV, YAML)

---

## Dependencies

```txt
pandas>=2.0.0           # Data manipulation
scipy>=1.11.0           # Statistical tests
numpy>=1.24.0           # Numerical operations
scikit-learn>=1.3.0     # K-means clustering
pyyaml>=6.0             # YAML output
```

---

## Examples

```bash
# Basic A/B test comparison
./box.sh analysis compare \
  --entities experiment_data.csv \
  --metrics metrics_config.yaml

# With custom output location
./box.sh analysis compare \
  --entities experiment_data.csv \
  --metrics metrics_config.yaml \
  --output results/comparison.yaml

# With strict NULL handling
./box.sh analysis compare \
  --entities experiment_data.csv \
  --metrics metrics_config.yaml \
  --null error

# With 99% confidence intervals
./box.sh analysis compare \
  --entities experiment_data.csv \
  --metrics metrics_config.yaml \
  --confidence 0.99

# Exploratory analysis with auto-detected clusters
./box.sh analysis analyze --entities customer_data.csv

# With specific number of clusters
./box.sh analysis analyze --entities customer_data.csv --clusters 4

# With sampling for faster k selection on large datasets
./box.sh analysis analyze --entities customer_data.csv --sampling 10

# With debug output
./box.sh analysis analyze --entities customer_data.csv --debug
```
