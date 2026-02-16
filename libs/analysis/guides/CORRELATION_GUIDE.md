# Understanding Correlations

A practical guide to interpreting correlation coefficients in experiment and exploratory analysis.

---

## What is Correlation?

**Correlation** measures how two variables change together. It answers: "When one variable changes, does the other tend to change in a predictable way?"

**Key point:** Correlation measures **association**, not causation. A strong correlation doesn't mean one variable causes the other.

---

## The Correlation Coefficient (r)

The correlation coefficient (r) is a number between **-1.0** and **+1.0** that quantifies the strength and direction of the relationship.

### Range and Meaning

```
-1.0                    0                    +1.0
 │                      │                      │
 │                      │                      │
Perfect negative     No relationship      Perfect positive
correlation                                 correlation
```

**Examples:**

| r value | Interpretation | What it means |
|---------|---------------|---------------|
| **+1.0** | Perfect positive | When X increases, Y **always** increases proportionally |
| **+0.7** | Strong positive | When X increases, Y **usually** increases substantially |
| **+0.4** | Moderate positive | When X increases, Y **often** increases somewhat |
| **+0.2** | Weak positive | When X increases, Y **sometimes** increases slightly |
| **0.0** | No correlation | X and Y are independent - no predictable relationship |
| **-0.2** | Weak negative | When X increases, Y **sometimes** decreases slightly |
| **-0.4** | Moderate negative | When X increases, Y **often** decreases somewhat |
| **-0.7** | Strong negative | When X increases, Y **usually** decreases substantially |
| **-1.0** | Perfect negative | When X increases, Y **always** decreases proportionally |

---

## Two Dimensions: Strength and Direction

### 1. Strength (Magnitude)

The **absolute value** |r| tells you how strong the relationship is:

```
|r| = 0.0 - 0.2    →  Very weak (almost no relationship)
|r| = 0.2 - 0.4    →  Weak (slight tendency)
|r| = 0.4 - 0.7    →  Moderate (noticeable pattern)
|r| = 0.7 - 1.0    →  Strong (clear, consistent pattern)
```

**Important:** Even a correlation of 0.2 might be meaningful in noisy real-world data!

### 2. Direction (Sign)

The **sign** (+ or -) tells you the direction:

- **Positive (+)**: Variables move together
  - Example: `agent_installed = 1` often means `subscribed = 1`
  - Both high together, or both low together

- **Negative (-)**: Variables move oppositely
  - Example: `time_to_first_event` high often means `converted = 0`
  - When one is high, the other tends to be low

---

## Concrete Example: Agent Installation

Let's say we measure correlation between `installed_agent` and `subscribed`:

**Scenario A: r = +0.54**
```
installed_agent:  1  1  1  1  0  0  0  0
subscribed:       1  1  1  0  0  0  1  0
                  ✓  ✓  ✓  ✗  ✓  ✓  ✗  ✓  → 5 out of 8 match
```
**Interpretation:** Moderate positive correlation. Orgs that install the agent are **more likely** to subscribe (but not guaranteed). This is a **moderate** effect - noticeable but not overwhelming.

**Scenario B: r = +0.05**
```
installed_agent:  1  1  1  1  0  0  0  0
subscribed:       0  1  1  0  1  0  0  1
                  ✗  ✓  ✓  ✗  ✗  ✓  ✓  ✗  → 4 out of 8 match (basically random)
```
**Interpretation:** Very weak positive correlation. Installing the agent has **almost no relationship** to subscribing. Knowing whether they installed tells you almost nothing about whether they'll subscribe.

**Scenario C: r = -0.42**
```
installed_agent:  1  1  1  1  0  0  0  0
subscribed:       0  0  1  0  1  1  1  0
                  ✗  ✗  ✓  ✗  ✓  ✓  ✓  ✓  → 5 out of 8 opposite
```
**Interpretation:** Moderate negative correlation. Orgs that install the agent are **less likely** to subscribe. This would be surprising and worth investigating!

---

## Statistical Significance vs Practical Significance

Two different questions:

### 1. Statistical Significance (p-value)

**Question:** "Is this correlation real, or just random noise?"

- **p < 0.05** (\*): Statistically significant - unlikely to be chance
- **p < 0.01** (\*\*): Very significant - very unlikely to be chance  
- **p < 0.001** (\*\*\*): Highly significant - almost certainly real

**Important:** With large datasets, even tiny correlations can be statistically significant!

### 2. Practical Significance (effect size)

**Question:** "Is this correlation large enough to matter?"

- **r = 0.05, p < 0.001**: Statistically significant but **practically meaningless**
  - Real pattern, but too weak to be useful
  - Example: "Signups on Tuesdays have 0.1% higher conversion" - true but irrelevant

- **r = 0.50, p < 0.001**: Both statistically and **practically significant**
  - Real pattern AND strong enough to act on
  - Example: "Orgs that complete onboarding have 50% higher retention" - actionable!

**Guideline:** Focus on correlations with **both**:
1. Statistical significance (p < 0.05)
2. Meaningful strength (|r| > 0.2 as a rough threshold)

---

## Types of Correlation We Compute

### Phi Coefficient (φ) - Binary × Binary

Used when both variables are binary (0/1, yes/no):

```
Example: installed_agent (0/1) × subscribed (0/1)

                subscribed=0    subscribed=1
installed=0         3000            500
installed=1          800            700

φ = 0.42 → Moderate positive correlation
```

**Interpretation:** Orgs that install the agent are moderately more likely to subscribe.

### Point-Biserial - Binary × Continuous

Used when one variable is binary, the other is continuous:

```
Example: subscribed (0/1) × revenue_m0 ($)

subscribed=0: avg revenue = $100
subscribed=1: avg revenue = $800

r_pb = 0.65 → Strong positive correlation
```

**Interpretation:** Subscribed orgs have substantially higher revenue (not surprising, they're paying!).

### Pearson's r - Continuous × Continuous

Used when both variables are continuous (not yet implemented in our library):

```
Example: time_to_first_event (minutes) × conversion_rate (%)

As time increases, conversion tends to decrease
r = -0.38 → Moderate negative correlation
```

---

## Common Misinterpretations

### ❌ "r = 0.9 means 90% of the relationship"
**Correct:** r = 0.9 means a very strong correlation. The percentage interpretation doesn't apply directly to r.

### ❌ "Positive correlation means both variables are high"
**Correct:** Positive correlation means they move together (both high OR both low). It's about **co-movement**, not absolute levels.

### ❌ "r = 0.2 is too small to care about"
**Correct:** In noisy real-world data, r = 0.2 can be meaningful! Consider the context and sample size.

### ❌ "High correlation means causation"
**Correct:** Correlation ≠ causation. High correlation could be due to:
- A causes B
- B causes A  
- C causes both A and B (confounding)
- Pure coincidence (less likely if p-value is small)

---

## When to Use Correlation Analysis

### ✅ Good Use Cases

1. **Exploratory analysis**: "What variables are related?"
2. **Feature discovery**: "What predicts our outcome of interest?"
3. **Hypothesis generation**: "What should we investigate further?"
4. **Sanity checks**: "Are expected relationships present?"

### ⚠️ Limitations

1. **Only linear relationships**: Doesn't capture complex non-linear patterns
2. **Outlier sensitive**: A few extreme values can skew results
3. **Not causal**: Can't tell you which variable influences which
4. **Binary/continuous only**: Our current implementation doesn't handle categorical variables with >2 levels

---

## Practical Interpretation Workflow

When you see a correlation result:

1. **Check strength** (|r| value)
   - < 0.2: Very weak, probably not useful
   - 0.2-0.4: Weak but might be interesting
   - 0.4-0.7: Moderate, worth investigating
   - > 0.7: Strong, likely important

2. **Check significance** (p-value)
   - p < 0.05: Likely real
   - p ≥ 0.05: Could be noise

3. **Check direction** (sign)
   - Positive: Variables move together
   - Negative: Variables move oppositely

4. **Consider context**
   - Sample size: Large n → even weak correlations significant
   - Domain knowledge: Does the relationship make sense?
   - Actionability: Can you do something with this insight?

5. **Follow up**
   - Strong correlations → Deep dive, understand mechanism
   - Unexpected correlations → Investigate, might be a bug or insight
   - Weak but significant → Lower priority, but keep in mind

---

## Examples from Our Output

### Example 1: Strong Actionable Correlation
```
installed_agent_x_subscribed
  ░░░░░░░░░░█████░░░░░ +0.540 ***
  Moderate positive correlation (highly significant)
```

**Interpretation:**
- **Bar (5 blocks right of center)**: Moderate strength - clear pattern
- **r = +0.540**: Moderate positive - variables move together
- **\*\*\***: p < 0.001 - almost certainly real, not noise
- **Actionable**: Installing agent is moderately predictive of subscription
- **Next step**: This is strong enough to prioritize agent install in onboarding

### Example 2: Statistically Significant but Weak
```
datacenter_us1_x_subscribed
  ░░░░░░░░░░█░░░░░░░░░ +0.120 **
  Weak positive correlation (very significant)
```

**Interpretation:**
- **Bar (1 block right of center)**: Weak strength - slight tendency
- **r = +0.120**: Weak positive - subtle relationship
- **\*\***: p < 0.01 - statistically significant
- **Less actionable**: Datacenter has only slight effect on subscription
- **Next step**: Lower priority; might be confounded with other factors (e.g., company size, timezone)

### Example 3: Not Significant
```
has_rum_data_x_subscribed
  ░░░░░░░░░░░░░░░░░░░░ +0.015 ns
  Very weak positive correlation
```

**Interpretation:**
- **Bar (empty - centered)**: Very weak - essentially no relationship
- **r = +0.015**: Nearly zero correlation
- **ns**: p ≥ 0.05 - could easily be random noise
- **Not actionable**: No evidence of relationship
- **Next step**: Ignore; no useful signal here

### Example 4: Negative Correlation
```
time_to_first_event_x_converted
  ░░░░░▓▓▓▓▓░░░░░░░░░░ -0.550 ***
  Moderate negative correlation (highly significant)
```

**Interpretation:**
- **Bar (5 blocks left of center)**: Moderate strength, negative direction
- **r = -0.550**: Moderate negative - variables move opposite
- **\*\*\***: p < 0.001 - almost certainly real
- **Actionable**: Longer time to first event strongly predicts lower conversion
- **Next step**: Focus on reducing time to first meaningful action

---

## Visual Legend

Our correlation output uses **centered progress bars** to show strength and direction:

```
Bar Structure (20 characters, center at position 10):
         ┌─ Center (zero correlation)
         ↓
░░░░░░░░░░░░░░░░░░░░  r = 0.0    (no correlation)

░░░░░░░░░░█░░░░░░░░░  r = +0.1   (very weak positive)
░░░░░░░░░░███░░░░░░░  r = +0.3   (weak positive)
░░░░░░░░░░█████░░░░░  r = +0.5   (moderate positive)
░░░░░░░░░░████████░░  r = +0.8   (strong positive)

░░░░░░░░░▓░░░░░░░░░░  r = -0.1   (very weak negative)
░░░░░░░▓▓▓░░░░░░░░░░  r = -0.3   (weak negative)
░░░░░▓▓▓▓▓░░░░░░░░░░  r = -0.5   (moderate negative)
░░▓▓▓▓▓▓▓▓░░░░░░░░░░  r = -0.8   (strong negative)
```

**How to Read:**
- **Center = zero**: No correlation starts at the middle
- **Positive (█)**: Grows **right** from center
- **Negative (▓)**: Grows **left** from center  
- **Length**: Distance from center = strength
- **Threshold**: Correlations < 0.1 barely visible (filters noise)

**Complete Format:**
```
correlation_name
  ░░░░░░░░░░█████░░░░░ +0.500 ***
  Moderate positive correlation (highly significant)
```

**Significance Indicators:**
- `***` = p < 0.001 (highly significant - almost certainly real)
- `**` = p < 0.01 (very significant - very likely real)
- `*` = p < 0.05 (significant - likely real)
- `ns` = p ≥ 0.05 (not significant - could be noise)

---

## Summary

**Key Takeaways:**

1. Correlation coefficient (r) ranges from -1 to +1
2. **Magnitude** (|r|) = strength (shown by bar length); **Sign** (+/-) = direction (left vs right fill)
3. **Statistical significance** (p-value) ≠ **practical significance** (effect size)
4. Focus on correlations that are both significant AND meaningful (|r| > ~0.2)
5. Correlation does not prove causation
6. Context matters - domain knowledge helps interpret results

**Rule of Thumb:**

- |r| < 0.2 and/or p > 0.05 → **Ignore** (noise or too weak)
- 0.2 < |r| < 0.4 and p < 0.05 → **Note** (interesting but not urgent)
- |r| > 0.4 and p < 0.05 → **Investigate** (strong enough to act on)

---

**For More Details:**

- Statistical tests: `libs/stats/statistics.py`
- Correlation analysis: `libs/stats/correlations.py`
- Usage guide: `libs/README.md`

**References:**

- Cohen, J. (1988). Statistical Power Analysis for the Behavioral Sciences
- Field, A. (2013). Discovering Statistics Using IBM SPSS Statistics

