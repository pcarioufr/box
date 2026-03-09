---
name: sync
description: Pull external documents (Google Docs, Confluence) to local markdown. Handles Google URLs, Confluence URLs, or both.
---

# Sync Skill

You are helping the user pull external documents to local markdown files. This skill handles:
- **Google Docs** - Via browser-based Apps Script with local callback
- **Confluence pages** - Via REST API v2

## Request Routing

Analyze the user's input to determine what to pull:

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

## CLI Commands

### Google Docs

```bash
# Pull a Google Doc (opens browser for auth, receives content via callback)
./box.sh google pull <id-or-url> -o <path>

# Examples
./box.sh google pull "1abc123..." -o data/project/               # Auto-slug filename from doc title
./box.sh google pull "https://docs.google.com/..." -o doc.md     # Specific filename
./box.sh google pull "1abc123..."                                 # Current directory
```

### Confluence

```bash
# Pull a Confluence page (REST API, requires ATLASSIAN_EMAIL and ATLASSIAN_TOKEN)
./box.sh confluence pull <url> -o <path>

# Examples
./box.sh confluence pull "https://datadoghq.atlassian.net/wiki/spaces/TEAM/pages/123/Title" -o data/project/
./box.sh confluence pull "https://datadoghq.atlassian.net/wiki/spaces/UO/overview" -o data/project/

# Clean Confluence markdown (remove custom tags)
./box.sh confluence clean input.md -o cleaned.md
```

## Workflows

### Pull a Google Doc

1. **Extract doc ID** from URL (or use raw ID)
2. **Run pull**:
   ```bash
   ./box.sh google pull "<id-or-url>" -o <output-path>
   ```
3. **Tell user**: "Browser opened for Google auth. File will be saved once the callback completes."

### Pull a Confluence Page

1. **Run pull**:
   ```bash
   ./box.sh confluence pull "<url>" -o <output-path>
   ```
2. **Report result**: Tell user where the file was saved.

### Pull Both

If user provides multiple URLs or asks to "sync everything", run the appropriate pull commands for each.

## Frontmatter

Both tools embed source identifiers in YAML frontmatter for future push support:

- **Google**: `google_id` field
- **Confluence**: `confluence_id` and `confluence_url` fields

## URL Patterns

### Google Doc URLs
- `https://docs.google.com/document/d/1abc123.../edit` → ID is `1abc123...`
- `https://drive.google.com/file/d/1xyz789.../view` → ID is `1xyz789...`
- Raw ID: `1abc123...` (44-character string)

### Confluence URLs
- `https://datadoghq.atlassian.net/wiki/spaces/SPACE/pages/123456789/Page+Title` → Page ID is `123456789`
- `https://datadoghq.atlassian.net/wiki/spaces/SPACE/overview` → Resolves to space homepage
- Blog posts: `https://datadoghq.atlassian.net/wiki/spaces/~/blog/2024/01/01/456/Title`

## Confluence-Specific Notes

### Blog Posts
Blog posts are supported via the REST API:
```bash
./box.sh confluence pull "<blog-url>" -o data/project/
```

### Markdown Cleaning
Confluence markdown contains special XML-like tags. To clean for read-only use:
```bash
./box.sh confluence clean data/my-page.md -o cleaned.md
```

## Google-Specific Notes

### Browser-Based Pull
Google pull uses a local callback server:
1. CLI starts HTTP server on a random port
2. Opens webhook URL in browser with doc ID and callback URL
3. Browser handles Google auth (restricted to "Only myself")
4. Apps Script converts doc and POSTs content back to local server
5. CLI receives content and saves to output path

## Best Practices

1. **Use `-o` with a directory** when you want auto-slugified filenames from the doc title
2. **Use `-o` with a file path** when you want a specific name
3. **Report output paths**: Always tell user where files are saved
