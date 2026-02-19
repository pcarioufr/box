# Datadog RUM CLI Tools

Command-line tools for querying Datadog Real User Monitoring (RUM) data, creating notebooks, and fetching session timelines.

## Commands

```bash
# Query RUM events
./box.sh datadog rum query "@type:view" --from-time 7d --output views.csv

# Aggregate RUM data (top N and time series)
./box.sh datadog rum aggregate "@type:view" --from-time 30d --group-by @view.name --limit 10

# Create/update notebooks
./box.sh datadog notebook create notebook.json
./box.sh datadog notebook update notebook.json

# Fetch session timelines
./box.sh datadog fetch session abc-123-def-456 -o session.yaml
./box.sh datadog fetch sessions --views "@view.url_path:/dashboard/*" --from-time 7d --limit 50
```

## Environment Variables

Required for all commands:
```bash
DD_API_KEY=your-api-key
DD_APP_KEY=your-app-key
DD_SITE=datadoghq.com  # or datadoghq.eu, us5.datadoghq.com, etc.
```

Set these in `.env` at the project root.

## Best Practices

### 1. Always Filter for Customers

Unless explicitly asked otherwise, always include customer-only filters:
- `@session.type:user` - Real users only (excludes synthetic monitoring)
- `@usr.is_datadog_employee:false` - Exclude internal traffic

**Example:**
```bash
./box.sh datadog rum aggregate \
  "@type:view @session.type:user @usr.is_datadog_employee:false" \
  --from-time 7d --group-by @view.name --limit 10
```

See `knowledge/datadog/model.md` for business context on what these filters mean.

### 2. Choose Appropriate Time Ranges

- **Recent activity:** `1h`, `24h` - For real-time monitoring
- **Weekly trends:** `7d` - For weekly patterns
- **Monthly analysis:** `30d` - For broader trends
- **Quarterly reports:** `90d` - For long-term analysis

### 3. Use Cardinality for Unique Counts

When counting unique users, sessions, or organizations:
```bash
--metric @usr.id --aggregation cardinality
```

**Available aggregations:** `count`, `cardinality`, `sum`, `avg`, `min`, `max`, `pc75`, `pc90`, `pc95`, `pc98`, `pc99`

### 4. Understand Bucket Capacity and Dimension Multiplication

**IMPORTANT: Dimensions multiply bucket usage**

Each dimension in `--group-by` multiplies the bucket count:
- `--group-by @usr.org_id --limit 10` → 10 buckets
- `--group-by @usr.org_id @usr.org_name --limit 10` → 10×10 = 100 buckets (!)
- `--group-by @usr.org_id @usr.org_name @geo.country --limit 10` → 10×10×10 = 1,000 buckets

**Aggregate queries are capped at 1,000 buckets**, so be strategic about dimensions.

#### Best practice: Only group by IDs for efficiency

```bash
# ✅ EFFICIENT: Only group by org_id (10 buckets)
./box.sh datadog rum aggregate "@type:view @session.type:user @usr.is_datadog_employee:false" \
  --from-time 7d \
  --group-by @usr.org_id \
  --metric @usr.id \
  --aggregation cardinality \
  --limit 10

# ❌ WASTEFUL: Grouping by both ID and name (100 buckets for same information)
./box.sh datadog rum aggregate "@type:view @session.type:user @usr.is_datadog_employee:false" \
  --from-time 7d \
  --group-by @usr.org_id @usr.org_name \
  --metric @usr.id \
  --aggregation cardinality \
  --limit 10
```

#### Why grouping by ID+name wastes buckets

Under the hood, the query engine:
1. Finds top 10 org_ids
2. For each org_id, finds top 10 org_names (which is always just 1 name per id)

Result: 10×10 = 100 buckets used when only 10 are needed.

#### When to include multiple dimensions

Only add dimensions when they create **actual aggregation**:

```bash
# ✅ GOOD: Each country has multiple cities (real aggregation)
--group-by @geo.country @geo.city

# ✅ GOOD: Each org has multiple users (real aggregation)
--group-by @usr.org_id @usr.id

# ❌ BAD: Each org_id has exactly one org_name (no real aggregation)
--group-by @usr.org_id @usr.org_name
```

#### Trade-off: Readability vs. Efficiency

If you need org names for presentation:
- **Option 1 (Efficient)**: Group by ID only, then look up names separately
- **Option 2 (Convenient)**: Accept the bucket cost and group by both for immediate readability

For most queries, prefer efficiency and group by IDs only.

### 5. Sort Appropriately

- `--sort desc` - Top N (highest values first) - **default**
- `--sort asc` - Bottom N (lowest values first)
- `--sort none` - Lexicographic order (alphabetical)

### 6. Discover Exact Syntax First

**Before making specific queries, discover the actual naming conventions.**

When querying for specific features or pages:
1. First aggregate by the relevant facet to see what values exist
2. Then use the discovered syntax for targeted queries

#### For actions (`@type:action`)

```bash
# First: Discover what action names exist
./box.sh datadog rum aggregate "@type:action @session.type:user @usr.is_datadog_employee:false" \
  --from-time 7d \
  --group-by @action.name \
  --limit 20

# Then: Query with the exact action name
./box.sh datadog rum aggregate "@type:action @action.name:*insight* @session.type:user @usr.is_datadog_employee:false" \
  --from-time 30d \
  --group-by @usr.org_id \
  --limit 10
```

#### For views (`@type:view`)

```bash
# First: Discover what view names or paths exist
./box.sh datadog rum aggregate "@type:view @session.type:user @usr.is_datadog_employee:false" \
  --from-time 7d \
  --group-by @view.name \
  --limit 20

# Or discover by view path
./box.sh datadog rum aggregate "@type:view @session.type:user @usr.is_datadog_employee:false" \
  --from-time 7d \
  --group-by @view.url_path \
  --limit 20

# Then: Query with the exact view name or path
./box.sh datadog rum aggregate "@type:view @view.url_path:/logs @session.type:user @usr.is_datadog_employee:false" \
  --from-time 30d \
  --group-by @usr.org_id \
  --limit 10
```

#### When in doubt

- Ask the user for clarification on the exact feature, page, or action name
- Use discovery queries to understand the data before making assumptions

#### Example - User asks: "Top orgs using watchdog insights in log explorer"

- "in the log explorer" → `@view.url_path:/logs` (not `@view.name:*log*explorer*`)
- "watchdog insights" → `@action.name:*insight*` for insight-related actions
- Correct query: Actions on insights within the logs view path

## Business Context

For business-specific information about your Datadog setup:
- **Field reference and query patterns**: See `knowledge/datadog/model.md`
- **Notebook API format**: See `libs/datadog/NOTEBOOKS.md`

## Output Tracking

Query results are saved to:
```
data/YYYY-MM-DD_investigation-name/
├── rum_query_TIMESTAMP.csv
├── rum_aggregate_TIMESTAMP.csv
└── sessions/
    ├── session_abc-123.yaml
    └── query.json
```

This creates an audit trail and enables reuse by other tools or analyses.
