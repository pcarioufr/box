/**
 * =================================================================
 * GOOGLE DOCS TO MARKDOWN CONVERTER (v4.0)
 * =================================================================
 *
 * USAGE:
 * Deploy as Web App ("Only myself") and call with a single doc ID:
 *   GET https://YOUR_URL/exec?id=docId&callback=http://localhost:PORT
 *
 * FLOW:
 * 1. CLI starts a local HTTP server and opens this URL in the browser
 * 2. Browser authenticates with Google (restricted to "Only myself")
 * 3. This script converts the doc to markdown
 * 4. Returns an HTML page with JS that POSTs the content to the callback URL
 * 5. CLI receives the content and saves it locally
 *
 * FEATURES:
 * - Converts Google Docs to Markdown with YAML frontmatter (includes google_id)
 * - Browser-based auth (no token needed, restricted to "Only myself")
 * - Callback to local CLI server (no file download needed)
 * - Includes threaded comments as appendix
 * - Strips base64 images by default
 *
 * VERSION HISTORY:
 * v3.1 - @pierre.cariou - 08-MAR-2026 - Callback to local server (no download/Drive)
 * v3.0 - @pierre.cariou - 08-MAR-2026 - Direct download (no Drive folder dependency)
 * v2.1 - @pierre.cariou - 05-FEB-2026 - Write to Drive folder (auth-friendly)
 * v2.0 - @pierre.cariou - 05-FEB-2026 - On-demand conversion via webhook
 */

// -----------------------------------------------------------------
// CONFIGURATION
// -----------------------------------------------------------------
var CONFIG = {
  // Set to TRUE to strip all base64 images from output
  REMOVE_IMAGES: true,

  // Set to TRUE to skip resolved comments in the appendix
  SKIP_RESOLVED_COMMENTS: false
};


// =================================================================
// WEBHOOK ENDPOINT
// =================================================================

/**
 * Webhook endpoint for GET requests.
 * Usage: GET https://YOUR_URL/exec?id=docId
 */
function doGet(e) {
  return handleWebhookRequest(e);
}

/**
 * Handles webhook request.
 * Converts a single doc to markdown and POSTs it to the callback URL.
 */
function handleWebhookRequest(e) {
  var docId = e.parameter.id || '';
  var callbackUrl = e.parameter.callback || '';

  if (!docId) {
    return htmlResponse("Error", "Missing required parameter: id");
  }
  if (!callbackUrl) {
    return htmlResponse("Error", "Missing required parameter: callback");
  }

  try {
    var result = convertDoc(docId);
    if (result.error) {
      return htmlResponse("Error", result.error);
    }

    // Return HTML page that POSTs content to the local CLI server
    return callbackResponse(callbackUrl, result.slug + '.md', result.content);

  } catch (err) {
    Logger.log("Error: " + err.toString());
    return htmlResponse("Error", err.toString());
  }
}

/**
 * Returns an HTML error page.
 */
function htmlResponse(title, body) {
  var html = '<!DOCTYPE html><html><head><meta charset="utf-8">' +
    '<title>' + title + '</title>' +
    '<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:40px auto;padding:20px;line-height:1.6}' +
    'h1{color:#333}.error{color:#cb2431}</style></head>' +
    '<body><h1>' + title + '</h1><p class="error">' + body + '</p></body></html>';
  return HtmlService.createHtmlOutput(html);
}

/**
 * Returns an HTML page that POSTs the markdown content to the CLI's local server.
 */
function callbackResponse(callbackUrl, filename, content) {
  // Encode content as JSON-safe string
  var payload = JSON.stringify({
    filename: filename,
    content: content
  });

  // Escape for embedding in JS string literal
  var escapedPayload = payload
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '\\r');

  var html = '<!DOCTYPE html><html><head><meta charset="utf-8">' +
    '<title>Sending...</title>' +
    '<style>body{font-family:system-ui,sans-serif;max-width:600px;' +
    'margin:80px auto;text-align:center;color:#333}' +
    '#status{font-size:1.2em}</style></head>' +
    '<body>' +
    '<p id="status">Sending to CLI...</p>' +
    '<script>' +
    'fetch(\'' + callbackUrl + '\', {' +
    '  method: "POST",' +
    '  headers: {"Content-Type": "application/json"},' +
    '  body: \'' + escapedPayload + '\'' +
    '}).then(function(r) {' +
    '  return r.text();' +
    '}).then(function(html) {' +
    '  document.open(); document.write(html); document.close();' +
    '}).catch(function(err) {' +
    '  document.getElementById("status").innerHTML = ' +
    '    "Failed to send to CLI: " + err.message + "<br><small>Is the CLI still running?</small>";' +
    '  document.getElementById("status").style.color = "#cb2431";' +
    '});' +
    '</script>' +
    '</body></html>';

  return HtmlService.createHtmlOutput(html);
}


// =================================================================
// CORE CONVERSION
// =================================================================

/**
 * Converts a Google Doc to markdown and returns the content.
 *
 * @param {string} docId - The Google Doc ID
 * @returns {Object} - {id, title, slug, content} or {id, error}
 */
function convertDoc(docId) {
  try {
    var file = DriveApp.getFileById(docId);
    var title = file.getName();
    var slug = slugify(title);

    // Generate frontmatter
    var frontMatter = generateFrontMatter(file);

    // Fetch markdown content from Google's export API
    var exportUrl = "https://docs.google.com/feeds/download/documents/export/Export?id=" + docId + "&exportFormat=markdown";
    var response = UrlFetchApp.fetch(exportUrl, {
      headers: { Authorization: "Bearer " + ScriptApp.getOAuthToken() },
      muteHttpExceptions: true
    });

    if (response.getResponseCode() !== 200) {
      return { id: docId, error: "Export failed (HTTP " + response.getResponseCode() + ")" };
    }

    var mdContent = frontMatter + processExportBlob(response.getBlob());

    // Clean images if configured
    if (CONFIG.REMOVE_IMAGES) {
      mdContent = removeBase64Images(mdContent);
    }

    // Append comments
    var comments = fetchFormattedComments(docId);
    if (comments) {
      mdContent += "\n\n" + comments;
    }

    return { id: docId, title: title, slug: slug, content: mdContent };

  } catch (e) {
    return { id: docId, error: e.toString() };
  }
}

/**
 * Process the export blob (handles both single file and zipped tabs).
 */
function processExportBlob(blob) {
  var contentType = blob.getContentType();

  if (contentType === 'application/zip' || contentType === 'application/x-zip-compressed') {
    // Multi-tab document - unzip and concatenate
    var unzipped = Utilities.unzip(blob);
    unzipped.sort(function(a, b) { return a.getName().localeCompare(b.getName()); });

    var content = '';
    for (var i = 0; i < unzipped.length; i++) {
      var tabBlob = unzipped[i];
      if (!tabBlob.getName().endsWith(".md")) continue;

      var tabName = tabBlob.getName().replace(".md", "");
      content += "# " + tabName + "\n\n" + tabBlob.getDataAsString() + "\n\n---\n\n";
    }
    return content;
  }

  // Single document
  return blob.getDataAsString();
}

/**
 * Remove base64-encoded images from markdown.
 */
function removeBase64Images(content) {
  // Reference definitions: [image1]: <data:...>
  content = content.replace(/^\[.*?\]:\s*<data:image\/[^>]+>/gm, "");
  // Reference links: ![][image1]
  content = content.replace(/!\[\]\[.*?\]/g, "> *[Image Removed]*");
  // Inline images: ![](data:...)
  content = content.replace(/!\[.*?\]\(data:[^)]+\)/g, "> *[Image Removed]*");
  // HTML img tags: <img src="data:...">
  content = content.replace(/<img[^>]+src=["']data:[^>]+>/g, "> *[Image Removed]*");
  return content;
}


// =================================================================
// HELPERS
// =================================================================

/**
 * Converts a string to a URL/filename-safe slug.
 */
function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[\s_]+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

/**
 * Generates YAML frontmatter for a document.
 */
function generateFrontMatter(file) {
  var title = file.getName();
  var id = file.getId();
  var created = Utilities.formatDate(file.getDateCreated(), Session.getScriptTimeZone(), "yyyy-MM-dd");

  var type = "gdoc";
  var source = "google-docs";

  // Detect special types
  var mime = file.getMimeType();
  var lowerTitle = title.toLowerCase();

  if (mime === MimeType.GOOGLE_SLIDES) {
    type = "gslide";
    source = "google-slides";
  } else if (lowerTitle.indexOf("notes by gemini") !== -1 || lowerTitle.indexOf("transcript") !== -1) {
    type = "meeting-transcript";
  }

  var safeTitle = title.replace(/"/g, '\\"');

  return "---\n" +
    "google_id: " + id + "\n" +
    "created: " + created + "\n" +
    "type: " + type + "\n" +
    "source: " + source + "\n" +
    'source_title: "' + safeTitle + '"\n' +
    "---\n\n";
}

/**
 * Fetches and formats comments from a document.
 */
function fetchFormattedComments(fileId) {
  var url = "https://www.googleapis.com/drive/v3/files/" + fileId + "/comments?" +
    "fields=comments(id,author(displayName),content,quotedFileContent,createdTime,resolved,replies(id,author(displayName),content,createdTime))&" +
    "pageSize=100";

  var response = UrlFetchApp.fetch(url, {
    headers: { Authorization: "Bearer " + ScriptApp.getOAuthToken() },
    muteHttpExceptions: true
  });

  if (response.getResponseCode() !== 200) {
    return "";
  }

  var data = JSON.parse(response.getContentText());
  var comments = data.comments;

  if (!comments || comments.length === 0) {
    return "";
  }

  var md = "---\n\n## Comments & Annotations\n\n";

  for (var i = 0; i < comments.length; i++) {
    var c = comments[i];

    if (CONFIG.SKIP_RESOLVED_COMMENTS && c.resolved) continue;

    var author = c.author ? c.author.displayName : "Unknown";
    var date = new Date(c.createdTime).toISOString().split('T')[0];

    // Quoted content
    var quote = "";
    if (c.quotedFileContent) {
      var qVal = typeof c.quotedFileContent === 'object' ? c.quotedFileContent.value : c.quotedFileContent;
      if (qVal) quote = "> " + qVal.replace(/\n/g, "\n> ") + "\n\n";
    }

    md += "### " + author + " (" + date + ")\n";
    md += quote;
    md += (c.content || "") + "\n\n";

    // Replies
    if (c.replies && c.replies.length > 0) {
      md += "**Replies:**\n";
      for (var j = 0; j < c.replies.length; j++) {
        var r = c.replies[j];
        md += "- **" + (r.author ? r.author.displayName : "Unknown") + "**: " + (r.content || "") + "\n";
      }
      md += "\n";
    }

    md += "---\n";
  }

  return md;
}
