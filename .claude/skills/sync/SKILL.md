---
name: sync
description: Sync external documents (Google Docs, Confluence) to local markdown. Handles Google URLs, Confluence URLs, or refreshes all entries.
---

# Sync Skill

You are helping the user sync external documents to local markdown files. This skill handles:
- **Google Docs** - Via browser-based Apps Script
- **Confluence pages** - Via MCP or REST API

## Request Routing

Analyze the user's input to determine what to sync:

### Google Doc URL
Detected by: `docs.google.com` or `drive.google.com` in URL

```
/sync https://docs.google.com/document/d/1abc123/edit
```

### Confluence URL
Detected by: `atlassian.net/wiki` in URL

```
/sync https://datadoghq.atlassian.net/wiki/spaces/TEAM/pages/12345/My+Doc
```

### Refresh All
Detected by: "refresh", "all", "everything", "sync all"

```
/sync refresh
/sync everything
```

### Refresh Google Only
Detected by: "refresh google", "google only", "just google"

```
/sync refresh google
```

### Refresh Confluence Only
Detected by: "refresh confluence", "confluence only", "just confluence"

```
/sync refresh confluence
```

## CLI Commands

### Google Docs

```bash
# List all Google entries
./box.sh google list

# Add a new entry (name derived from doc title)
./box.sh google add "<url>"

# Remove an entry (by doc ID or partial ID)
./box.sh google remove "1abc123"

# Refresh all Google entries (opens browser)
./box.sh google refresh
```

### Confluence

```bash
# List all Confluence entries
./box.sh confluence list

# Add a new entry
./box.sh confluence add "<url>" --name "my-page"

# Remove an entry
./box.sh confluence remove "my-page"

# Download a page directly (without adding to sync.yaml)
./box.sh confluence download "<url>" --name "my-page"

# Clean Confluence markdown (remove custom tags)
./box.sh confluence clean input.md -o cleaned.md
```

## Workflows

### Sync a Google Doc

1. **Check if already in sync.yaml**:
   ```bash
   ./box.sh google list
   ```

2. **If not found**, add to sync.yaml:
   ```bash
   ./box.sh google add "<url>"
   ```

3. **Trigger sync** via browser:
   ```bash
   ./box.sh google refresh
   ```

4. **Tell user**: "Browser opened - check the browser window for sync status. Files will sync to your Google Drive folder."

### Sync a Confluence Page

1. **Check if already in sync.yaml**:
   ```bash
   ./box.sh confluence list
   ```

2. **If found**: Just update that file (skip adding to config)

3. **If not found**:
   - Extract page ID from URL
   - Ask user for a name (suggest one based on URL title)
   - Add to sync.yaml: `./box.sh confluence add "<url>" --name "suggested-name"`

4. **Download the page** using MCP:
   ```javascript
   mcp__atlassian__getConfluencePage({
     cloudId: "datadoghq.atlassian.net",
     pageId: "<extracted-page-id>",
     contentFormat: "markdown"
   })
   ```

5. **Save to**: `data/_confluence/{name}.md`

### Refresh Everything

1. **Refresh Google** (opens browser):
   ```bash
   ./box.sh google refresh
   ```

2. **Refresh Confluence** (via MCP for each entry):
   ```bash
   ./box.sh confluence list
   ```
   Then download each entry via MCP and save to `data/_confluence/{name}.md`

3. **Report results**: "Synced 3 Google Docs (check browser) and 5 Confluence pages."

## Output Locations

- **Google Docs** → `data/_google/{slugified-title}.md`
- **Confluence** → `data/_confluence/{name}.md`

## URL Patterns

### Google Doc URLs
- `https://docs.google.com/document/d/1abc123.../edit` → ID is `1abc123...`
- `https://drive.google.com/file/d/1xyz789.../view` → ID is `1xyz789...`

### Confluence URLs
- `https://datadoghq.atlassian.net/wiki/spaces/SPACE/pages/123456789/Page+Title` → Page ID is `123456789`

## Confluence-Specific Notes

### Blog Posts
The MCP tool only works for regular pages, not blog posts (URLs with `/blog/`).

**For blog posts, use the CLI directly:**
```bash
./box.sh confluence download "<blog-url>" --name "my-blog-post"
```

### Markdown Format
Confluence markdown contains special XML-like tags. Keep these intact for read/write workflows. To clean for read-only use:
```bash
./box.sh confluence clean data/_confluence/my-page.md -o cleaned.md
```

### Cloud ID
The cloud ID is typically `datadoghq.atlassian.net`. Use `getAccessibleAtlassianResources` if needed.

## Google-Specific Notes

### Browser-Based Sync
Google sync uses a browser-based approach due to org authentication requirements:
1. CLI opens webhook URL in browser with doc IDs
2. Browser handles Google auth automatically
3. Apps Script converts docs to markdown
4. Files sync to Google Drive folder locally

### Timing
Files may take a moment to sync locally via Google Drive app after the browser sync completes.

## Example Sessions

**User:** `/sync https://docs.google.com/document/d/1abc123/edit`
**You:** Check google list, add if needed, run google refresh, tell user to check browser.

**User:** `/sync https://datadoghq.atlassian.net/wiki/spaces/TEAM/pages/12345/My+Doc`
**You:** Check confluence list, suggest name "my-doc", confirm with user, add to sync, download via MCP, save file.

**User:** `/sync refresh`
**You:** Run google refresh (tell user to check browser), then refresh all confluence entries via MCP, report results.

**User:** `/sync everything`
**You:** Same as refresh - sync all Google and Confluence entries.

## Best Practices

1. **Check before adding**: Always check if entry exists in sync.yaml first
2. **Confirm names**: For Confluence, suggest a name and confirm with user before adding
3. **Report browser actions**: Always tell user when browser opens for Google sync
4. **Report output paths**: Tell user where files are saved
