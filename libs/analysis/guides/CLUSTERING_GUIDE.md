# Understanding Clustering Analysis

A practical guide to interpreting cluster analysis results in exploratory data analysis.

---

## What is Clustering?

**Clustering** is an unsupervised machine learning technique that groups similar entities together based on their characteristics. It answers: "Are there natural groups or segments in my data?"

**Key point:** Clustering discovers **patterns** without being told what to look for. Unlike correlation (which measures relationships between variables), clustering identifies groups of **similar entities**.

---

## Why Use Clustering?

### ✅ Good Use Cases

1. **Customer segmentation**: "What types of users do we have?"
2. **Pattern discovery**: "Are there distinct behavior profiles?"
3. **Anomaly detection**: "Which entities don't fit any cluster?"
4. **Hypothesis generation**: "Do different segments behave differently?"
5. **Feature validation**: "Do our metrics actually separate users?"

### Example: Onboarding Analysis

Imagine analyzing 10,000 organizations that signed up. Clustering might reveal:

- **Cluster 0 (2,500 orgs)**: "Explorers" - installed agent, no data sent, didn't subscribe
- **Cluster 1 (5,000 orgs)**: "Dormant" - minimal activity, no agent, didn't subscribe  
- **Cluster 2 (2,000 orgs)**: "Engaged" - installed agent, sent data, high subscription rate
- **Cluster 3 (500 orgs)**: "Power users" - all features used, very high subscription rate

These segments can inform product strategy, onboarding flows, and intervention timing.

---

## K-Means Clustering: How It Works

Our library uses **K-means**, a popular clustering algorithm.

### Basic Algorithm

1. **Choose K**: Decide how many clusters to find (we auto-detect this!)
2. **Initialize**: Randomly place K "centroids" (cluster centers)
3. **Assign**: Each entity joins the nearest centroid
4. **Update**: Move centroids to the average of their members
5. **Repeat**: Steps 3-4 until centroids stop moving

### Visual Example (2D)

```
Initial data points:        After K-means (K=3):

    •  •                       🔴  🔴
  •  •  •                    🔴  🔴  🔴
    •                           🔴
                               
      •  •                         🟢  🟢
    •  •                         🟢  🟢

•  •                        🔵  🔵
  •  •                        🔵  🔵

Three natural groups      →  Three clusters identified
```

### What "Distance" Means

K-means measures similarity using **Euclidean distance** (straight-line distance in multi-dimensional space).

For binary features (0/1), distance is essentially "how many features differ?"

```
Entity A: [installed_agent=1, subscribed=1, has_data=0]
Entity B: [installed_agent=1, subscribed=0, has_data=0]
Distance: 1 feature differs (subscribed)

Entity C: [installed_agent=0, subscribed=0, has_data=1]
Distance from A: 3 features differ → more distant
```

---

## Finding the Optimal K

**Problem:** How many clusters should we look for?

**Solution:** We use the **silhouette score** to automatically find the best K.

### Silhouette Score

The silhouette score measures how well entities fit their assigned cluster:

```
Score range: -1.0 to +1.0

+1.0 → Perfect clustering (entities very close to their cluster, far from others)
 0.0 → Ambiguous (entities on border between clusters)
-1.0 → Mis-clustered (entities closer to wrong cluster)
```

**Our Process:**

1. Try K = 2, 3, 4, 5, 6, 7, 8, 9, 10
2. Compute silhouette score for each K
3. Choose K with the highest score

**Performance Note:**

Finding optimal K requires computing silhouette scores, which has **O(n²)** complexity (compares each entity to every other entity). For large datasets (> 10,000 entities), this can be slow.

**Solution: Sampling**

Use the `--sampling` option to speed up K selection without sacrificing quality:

```bash
# Use half the data for K selection
./run.sh analysis analyze --entities entities.sql --sampling 2

# Use 1/10th of the data for K selection  
./run.sh analysis analyze --entities entities.sql --sampling 10
```

**Important:** Sampling only affects the optimal K search. Once K is determined, the full dataset is used for final clustering.

**Example with 26,000 entities:**
- Without sampling: ~60 seconds for K selection
- With `--sampling 2` (13,000 entities): ~15 seconds (4× faster)
- With `--sampling 10` (2,600 entities): ~3 seconds (20× faster)

Silhouette scores are stable with representative samples, so `--sampling 2` or `--sampling 3` typically provides the same optimal K with much faster execution.

**Example Output:**
```yaml
optimal_k_search:
  k_values_tested: [2, 3, 4, 5, 6, 7, 8, 9, 10]
  silhouette_scores:
    k2: 0.324
    k3: 0.412  ← highest score
    k4: 0.387
    k5: 0.301
  optimal_k: 3
  optimal_silhouette: 0.412
```

**Interpretation:**
- **Silhouette > 0.5**: Strong, well-separated clusters
- **Silhouette 0.3-0.5**: Moderate clusters (typical for real-world data)
- **Silhouette < 0.3**: Weak clusters (data might not have clear structure)

In this example, K=3 gives the clearest separation.

---

## Interpreting Cluster Results

### 1. Cluster Sizes

```yaml
cluster_distribution:
  cluster_0:
    count: 5234
    percentage: 52.3%
  cluster_1:
    count: 3012
    percentage: 30.1%
  cluster_2:
    count: 1754
    percentage: 17.6%
```

**What to Look For:**
- **Balanced sizes** (e.g., 40%, 35%, 25%): Multiple meaningful segments
- **One dominant cluster** (e.g., 85%, 10%, 5%): Most entities similar, few outliers
- **Tiny clusters** (e.g., < 5%): Might be anomalies or edge cases

### 2. Cluster Profiles

**Default Output** (concise):

```yaml
clusters:
  cluster_0:
    size: 5234
    percentage: 52.34
    features:
      installed_agent: 0.00 ▓▓░░░░░░░░░░░░░░░░░ 1.00    ← Low: bar on left
      subscribed: 0.00 ▓░░░░░░░░░░░░░░░░░░ 1.00         ← Very low
      has_rum_data: 0.00 ▓░░░░░░░░░░░░░░░░░░ 1.00
    characteristics: "Low: installed_agent, subscribed, has_rum_data"
    
  cluster_1:
    size: 3012
    percentage: 30.12
    features:
      installed_agent: 0.00 ░░░░░░░░░░░░░░░▓▓▓░ 1.00    ← High: bar on right
      subscribed: 0.00 ░░░░░░░░░░░░░▓▓▓▓░░ 1.00         ← High
      has_rum_data: 0.00 ░░░░░░▓▓▓░░░░░░░░░░ 1.00       ← Moderate
    characteristics: "High: installed_agent, subscribed; Moderate: has_rum_data"
    
  cluster_2:
    size: 1754
    percentage: 17.54
    features:
      installed_agent: 0.00 ░░░░░░░░░░░░░░░░░▓▓ 1.00    ← Very high: bar far right
      subscribed: 0.00 ░░░░░░░░░░░░░░░░▓▓▓ 1.00         ← Very high
      has_rum_data: 0.00 ░░░░░░░░░░░░░░░▓▓▓░ 1.00       ← Very high
    characteristics: "High: installed_agent, subscribed, has_rum_data"
```

**Debug Output** (with `--debug` flag):

```yaml
clusters:
  cluster_0:
    size: 5234
    percentage: 52.34
    features:
      installed_agent:
        mean: 0.12
        std: 0.32
        min: 0.0
        max: 1.0
        distribution: 0.00 ▓▓░░░░░░░░░░░░░░░░░ 1.00
    characteristics: "Low: installed_agent, subscribed, has_rum_data"
    centroid:
      installed_agent: 0.12
      subscribed: 0.05
      has_rum_data: 0.03
```

**Interpretation:**

- **Cluster 0**: "Low-engagement" - didn't install, didn't subscribe (52% of orgs)
  - Distribution bars show values clustered near 0 (left side)
  
- **Cluster 1**: "Moderate adopters" - installed agent, many subscribed, some data (30%)
  - Distribution bars show mixed/middle-range values
  
- **Cluster 2**: "Power users" - high engagement across all metrics (18%)
  - Distribution bars show values clustered near 1 (right side)

**Key Insight:** The distribution bars visually confirm a clear progression: dormant → engaged → power users

**Note:** Use `--debug` to see detailed statistics (`mean`, `std`, `min`, `max`) for each feature. By default, only the distribution bar is shown for scannability.

---

## Complete Example: Interpreting Real Output

### Scenario: Agent Installation Analysis

**Default Output:**

```yaml
metadata:
  optimal_k: 3
  optimal_silhouette: 0.428
  n_entities: 10000

clusters:
  cluster_0:
    size: 5234
    percentage: 52.34
    features:
      installed_agent: 0.00 ▓░░░░░░░░░░░░░░░░░░ 1.00
      subscribed: 0.00 ▓░░░░░░░░░░░░░░░░░░ 1.00
      has_rum_data: 0.00 ▓░░░░░░░░░░░░░░░░░░ 1.00
    characteristics: "Low: installed_agent, subscribed, has_rum_data"
    
  cluster_1:
    size: 3012
    percentage: 30.12
    features:
      installed_agent: 0.00 ░░░░░░░░░░░░░░░░▓▓▓ 1.00
      subscribed: 0.00 ░░░░░░▓▓░░░░░░░░░░░ 1.00
      has_rum_data: 0.00 ░░░░▓▓░░░░░░░░░░░░ 1.00
    characteristics: "High: installed_agent; Moderate: subscribed, has_rum_data"
    
  cluster_2:
    size: 1754
    percentage: 17.54
    features:
      installed_agent: 0.00 ░░░░░░░░░░░░░░░░░▓▓ 1.00
      subscribed: 0.00 ░░░░░░░░░░░░░░░▓▓▓░ 1.00
      has_rum_data: 0.00 ░░░░░░░░░░░░░░▓▓▓░ 1.00
    characteristics: "High: installed_agent, subscribed, has_rum_data"
```

**Interpretation:** Moderate cluster separation (silhouette = 0.428) - clear but overlapping segments

### Step-by-Step Interpretation

**1. Cluster Quality**
- Silhouette = 0.428 → **Moderate** separation
- Three clusters found → Multiple distinct segments exist

**2. Segment Identification**
- **Cluster 0 (52%)**: "Dormant" - very low engagement, didn't install agent
  - Distribution bars clustered on left (near 0) for all features
- **Cluster 1 (30%)**: "Installed but exploring" - agent installed, mixed subscription
  - Agent install bar on right, but subscription/data bars in middle
- **Cluster 2 (18%)**: "Fully engaged" - installed, subscribed, sending data
  - All distribution bars clustered on right (near 1)

### Actionable Insights

1. **52% of users are dormant** → Focus onboarding on activation
2. **30% installed but didn't fully engage** → Investigate barriers to subscription
3. **18% are power users** → Study what they did differently

---

## Common Pitfalls

### ❌ "3 clusters means 3 types of users"

**Correct:** 3 clusters is our **model's** simplification. Reality is more of a spectrum, but 3 groups are easier to act on than 10,000 individuals.

### ❌ "Low silhouette score means clustering failed"

**Correct:** Real-world data is messy! Silhouette = 0.3 might be as good as it gets. Even fuzzy clusters can reveal useful patterns.

### ❌ "Cluster 0 is bad, Cluster 2 is good"

**Correct:** Cluster numbers are arbitrary. Focus on **profiles** (means), not numbers.

### ❌ "Clustering proves causation"

**Correct:** Clustering shows **correlation** within segments. It doesn't tell you why segments exist or what causes differences.

### ❌ "More clusters = better insights"

**Correct:** Too many clusters become unactionable. K=3-5 is usually most useful for decision-making.

---

## Clustering vs. Correlation

**Different questions:**

| Clustering | Correlation |
|------------|-------------|
| "Are there groups of similar entities?" | "Do two variables move together?" |
| Groups **entities** (rows) | Relates **variables** (columns) |
| Unsupervised (no target) | Measures relationship between specific pairs |
| Output: Segment profiles | Output: Strength + direction of relationship |

**Use together:**
1. **Clustering** → Discover user segments
2. **Correlation** (within segments) → Understand what drives behavior in each segment

---

## Practical Interpretation Workflow

When you see clustering results:

1. **Check cluster quality** (silhouette score)
   - > 0.5: Strong separation → trust the segments
   - 0.3-0.5: Moderate → segments are real but fuzzy
   - < 0.3: Weak → data might not have clear structure

2. **Review cluster sizes**
   - Look for balanced vs. dominant clusters
   - Tiny clusters (< 5%) might be outliers

3. **Examine cluster profiles**
   - Name each cluster based on its characteristics
   - Look for clear differences between clusters

4. **Check focus analysis** (if applicable)
   - p < 0.05: Focus variable separates clusters well
   - p ≥ 0.05: Focus variable doesn't explain clusters

5. **Check variant analysis** (if applicable)
   - p < 0.05: Experiment changed segment distribution
   - p ≥ 0.05: Similar segments in both variants

6. **Follow up**
   - Profile high-value clusters (what do they do differently?)
   - Design interventions to move users between clusters
   - A/B test strategies tailored to each segment

---

## Stratified Clustering: Finding Sub-Segments

**What is stratified clustering?**

When you use `--focus` with a **binary variable** (0/1), the analysis performs **stratified clustering**: it splits the data by that variable and clusters each group separately.

**Example:**

```bash
./run.sh analysis analyze \
  --entities entities.sql \
  --focus installed_agent
```

This answers: **"What types of users exist among those who installed vs. those who didn't?"**

### How It Works

1. **Split data** by focus variable:
   - `installed_agent=0` → 5,300 entities (76%)
   - `installed_agent=1` → 1,651 entities (24%)

2. **Cluster each group separately** (may find different optimal K):
   - Among non-installers (installed_agent=0): Find 2 clusters
   - Among installers (installed_agent=1): Find 2 clusters

3. **Profile each sub-cluster**:
   - Non-installer Cluster 0: Dormant (no activity)
   - Non-installer Cluster 1: Engaged without agent
   - Installer Cluster 0: Installed but inactive
   - Installer Cluster 1: Installed and active

### Why This Is Useful

**Standard clustering** answers: "What user segments exist overall?"
- Output: "Low engagement", "Medium engagement", "High engagement"

**Stratified clustering** answers: "What types exist within each group?"
- Output (non-installers): "Never engaged" vs "Engaged but didn't install"
- Output (installers): "Installed but inactive" vs "Power users"

**Actionable insights:**

```yaml
installed_agent_0:  # Non-installers (76%)
  cluster_0: 98.5%  # Never engaged → Target for initial activation
  cluster_1: 1.5%   # Engaged without agent → Push agent install

installed_agent_1:  # Installers (24%)
  cluster_0: 96.9%  # Installed but inactive → Re-engagement campaign
  cluster_1: 3.1%   # Power users → Study for best practices
```

This tells you **exactly which interventions to try** for each sub-segment!

### When to Use Stratified Clustering

✅ **Use stratified clustering when:**
- You want to understand **"what types exist within group X vs group Y?"**
- You're investigating a specific binary outcome (installed, converted, churned)
- You want to find root causes or barriers specific to each group

❌ **Don't use stratified clustering when:**
- Your focus variable isn't binary (use standard focus analysis instead)
- You want overall segmentation (use standard clustering without --focus)
- One group is very small (< 100 entities) - clustering won't be reliable

---

## Advanced: Fixing the Number of Clusters

By default, we auto-detect optimal K. But you can override:

```bash
./run.sh analysis analyze \
  --entities entities.sql \
  --clusters 5
```

**When to fix K:**
- You have domain knowledge (e.g., "We have 4 product tiers")
- You want consistent K across multiple analyses (for comparison)
- Auto-detected K seems too high/low for actionability

**Trade-off:**
- **Fewer clusters** (K=2-3): Simpler, more actionable, but might miss nuances
- **More clusters** (K=8-10): More detailed, but harder to act on

**Rule of thumb:** K=3-5 is the "Goldilocks zone" for most business decisions.

**Note:** In stratified clustering, K is auto-detected **independently** for each stratum, so you might get K=2 for one group and K=4 for another.

---

## Visual Legend

### Distribution Bars

Each cluster feature includes a **distribution bar** showing where this cluster sits in the global distribution.

**Default output** (concise):
```yaml
cluster_0:
  features:
    returned_after_7_days: 0.00 ▓▓▓▓▓░░░░░░░░░░░░░░░ 1.00
```

**Debug output** (with `--debug`):
```yaml
cluster_0:
  features:
    returned_after_7_days:
      mean: 0.031
      std: 0.174
      min: 0.0
      max: 1.0
      distribution: 0.00 ▓▓▓▓▓░░░░░░░░░░░░░░░ 1.00
```

**How to Read the Distribution Bar:**

```
<global_min> _░░░░▓▓▓▓▓░░░░░___ <global_max>
             ↑    ↑   ↑    ↑
             │    │   │    └─ cluster max
             │    │   └────── mean ± std
             │    └────────── cluster min
             └─────────────── outside cluster range
```

**Legend:**
- **`_`** (underscore) = Values outside this cluster's range
- **`░`** (light shade) = Cluster's min to max range
- **`▓`** (dark shade) = Mean ± standard deviation (the "typical" range)
- **Numbers** = Global min and max across ALL clusters

### Examples

**Binary feature (mostly 0s):**
```yaml
returned_after_7_days:
  mean: 0.031, std: 0.174
  distribution: 0.00 ▓▓▓▓▓░░░░░░░░░░░░░░░ 1.00
```
- Most entities (>95%) have value 0
- A few entities (~5%) have value 1
- The ▓ area shows the typical range (0.00 to ~0.20)

**Continuous feature with variation:**
```yaml
signup_session_clicks:
  mean: 3.7, std: 6.3, range: [0, 45]
  distribution: 0.00 ▓░░░________________ 240.00
```
- ▓ = typical range (0 to ~10 clicks)
- ░░░ = this cluster extends to 45 clicks
- ___ = values this cluster doesn't reach (global max is 240)
- **Insight**: This cluster has low-to-moderate click activity

**Constant feature (all zeros):**
```yaml
pageview_count:
  mean: 0.0, std: 0.0
  distribution: 0.00 ▓___________________ 557.00
```
- ▓ at position 0 = all entities in this cluster have exactly 0 pageviews
- ___ = this cluster has no variation (other clusters go up to 557)
- **Insight**: This is a "no pageview activity" cluster

**High-engagement cluster:**
```yaml
signup_session_clicks:
  mean: 45.2, std: 18.7, range: [15, 120]
  distribution: 0.00 _______░░░▓▓▓▓▓▓░░░_ 240.00
```
- ___ = cluster starts at 15 (skips the low range)
- ░░░ = cluster range (15 to 120)
- ▓▓▓▓▓▓ = typical range (30 to 65 clicks)
- **Insight**: This is a "high-engagement" cluster

### What the Distribution Bar Tells You

**At a glance, you can see:**

1. **Position**: Where does this cluster sit in the overall distribution?
   - Left side (near global min) = low values
   - Right side (near global max) = high values
   - Spans full range = mixed cluster

2. **Spread**: How varied is this cluster?
   - Narrow ▓ = consistent values (low std)
   - Wide ▓ = varied values (high std)
   - Small ░ range = homogeneous cluster

3. **Gaps**: Which parts of the range does this cluster NOT occupy?
   - ___ on left = cluster doesn't have low values
   - ___ on right = cluster doesn't have high values
   - ___ in middle = cluster avoids mid-range values

4. **Overlap**: Do clusters occupy different ranges?
   - No overlap = well-separated clusters
   - Overlap = fuzzy boundaries between clusters

### Numeric Values

**Default output:**
```yaml
clusters:
  cluster_0:
    features:
      installed_agent: 0.00 ▓▓░░░░░░░░░░░░░░░░░ 1.00    ← 12% installed
      
  cluster_1:
    features:
      installed_agent: 0.00 ░░░░░░░░░░░░░░░▓▓▓░ 1.00    ← 89% installed
```

**Debug output** (with `--debug`):
```yaml
clusters:
  cluster_0:
    features:
      installed_agent:
        mean: 0.12     ← 12% of entities in this cluster have installed_agent=1
        std: 0.32
        min: 0.0
        max: 1.0
        distribution: 0.00 ▓▓░░░░░░░░░░░░░░░░░ 1.00
      
  cluster_1:
    features:
      installed_agent:
        mean: 0.89     ← 89% of entities in this cluster have installed_agent=1
        std: 0.31
        min: 0.0
        max: 1.0
        distribution: 0.00 ░░░░░░░░░░░░░░░▓▓▓░ 1.00
```

**How to Read:**
- In default mode, the distribution bar position tells you the approximate mean
  - Bar on left (▓ near 0.00) → Low mean (close to 0)
  - Bar in middle → Moderate mean (around 0.5)
  - Bar on right (▓ near 1.00) → High mean (close to 1)
- In debug mode, exact `mean`, `std`, `min`, and `max` values are provided
- **For binary features**, the mean is the **percentage** that have the feature

---

## Summary

**Key Takeaways:**

1. Clustering groups similar entities to reveal natural segments
2. **Silhouette score** (0.3-0.5 typical) measures cluster quality
3. **K-means** finds K groups by minimizing within-cluster distance
4. **Cluster profiles** (means) characterize each segment
5. **Focus analysis** tests if a variable separates clusters
6. **Variant analysis** tests if experiment changed segment distribution
7. Clustering discovers patterns; follow-up analysis explains them

**Rule of Thumb:**

- Silhouette > 0.3 → **Use clustering** to guide strategy
- Focus p < 0.05 → **Focus variable explains** segments well
- Variant p < 0.05 → **Experiment changed** user composition/behavior

---

**For More Details:**

- Clustering implementation: `libs/stats/clustering.py`
- Statistical tests: `libs/stats/statistics.py`
- Usage guide: `libs/README.md`

**References:**

- MacQueen, J. (1967). "Some methods for classification and analysis of multivariate observations"
- Rousseeuw, P. J. (1987). "Silhouettes: A graphical aid to the interpretation and validation of cluster analysis"
- Jain, A. K. (2010). "Data clustering: 50 years beyond K-means"


