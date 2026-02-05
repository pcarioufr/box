/**
 * =================================================================
 * GOOGLE DOCS TO MARKDOWN CONVERTER (v2.1)
 * =================================================================
 *
 * USAGE:
 * Deploy as Web App and call with specific doc IDs:
 *   GET https://YOUR_URL/exec?ids=docId1,docId2
 *
 * OUTPUT:
 * Markdown files are written to OUTPUT_FOLDER_ID in Google Drive.
 * Use Google Drive app to sync files locally.
 *
 * FEATURES:
 * - Converts Google Docs to Markdown with YAML frontmatter
 * - Writes files to Drive folder with slugified filenames
 * - Includes threaded comments as appendix
 * - Strips base64 images by default
 *
 * VERSION HISTORY:
 * v2.1 - @pierre.cariou - 05-FEB-2026 - Write to Drive folder (auth-friendly)
 * v2.0 - @pierre.cariou - 05-FEB-2026 - On-demand conversion via webhook
 */

// -----------------------------------------------------------------
// CONFIGURATION
// -----------------------------------------------------------------
var CONFIG = {
  // Google Drive folder ID where markdown files will be saved
  // Get this from the folder URL: https://drive.google.com/drive/folders/FOLDER_ID
  OUTPUT_FOLDER_ID: '1ejAFfdSzGZ2aekKnC3W6kVEWAemAUuNl',

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
 * Usage: GET https://YOUR_URL/exec?ids=id1,id2,id3
 */
function doGet(e) {
  return handleWebhookRequest(e);
}

/**
 * Webhook endpoint for POST requests.
 */
function doPost(e) {
  return handleWebhookRequest(e);
}

/**
 * Handles webhook requests.
 * Converts docs and writes to Drive folder, returns HTML status page.
 */
function handleWebhookRequest(e) {
  // Check config
  if (!CONFIG.OUTPUT_FOLDER_ID) {
    return htmlResponse("Error", "OUTPUT_FOLDER_ID not configured in script.");
  }

  // Require ids parameter
  var idsParam = e.parameter.ids || '';
  if (!idsParam) {
    return htmlResponse("Error", "Missing required parameter: ids (comma-separated doc IDs)");
  }

  try {
    var docIds = idsParam.split(',')
      .map(function(id) { return id.trim(); })
      .filter(function(id) { return id !== ''; });

    if (docIds.length === 0) {
      return htmlResponse("Error", "No valid doc IDs provided");
    }

    var folder = DriveApp.getFolderById(CONFIG.OUTPUT_FOLDER_ID);
    var results = [];

    for (var i = 0; i < docIds.length; i++) {
      var result = convertAndSaveDoc(docIds[i], folder);
      results.push(result);
    }

    return htmlResponse("Sync Complete", formatResults(results));

  } catch (err) {
    Logger.log("Error: " + err.toString());
    return htmlResponse("Error", err.toString());
  }
}

/**
 * Returns an HTML response page.
 */
function htmlResponse(title, body) {
  var html = '<!DOCTYPE html><html><head><meta charset="utf-8">' +
    '<title>' + title + '</title>' +
    '<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:40px auto;padding:20px;line-height:1.6}' +
    'h1{color:#333}pre{background:#f5f5f5;padding:15px;border-radius:5px;overflow-x:auto}' +
    '.success{color:#22863a}.error{color:#cb2431}</style></head>' +
    '<body><h1>' + title + '</h1>' + body + '</body></html>';
  return HtmlService.createHtmlOutput(html);
}

/**
 * Formats results as HTML.
 */
function formatResults(results) {
  var html = '<p>Processed ' + results.length + ' document(s):</p><ul>';
  for (var i = 0; i < results.length; i++) {
    var r = results[i];
    if (r.error) {
      html += '<li class="error">❌ ' + r.id + ': ' + r.error + '</li>';
    } else {
      html += '<li class="success">✅ ' + r.slug + '.md (' + r.title + ')</li>';
    }
  }
  html += '</ul><p>Files saved to Drive folder. Google Drive app will sync them locally.</p>';
  html += '<p><small>Timestamp: ' + new Date().toISOString() + '</small></p>';
  return html;
}


// =================================================================
// CORE CONVERSION
// =================================================================

/**
 * Converts a Google Doc to markdown and saves to folder.
 *
 * @param {string} docId - The Google Doc ID
 * @param {Folder} folder - The Drive folder to save to
 * @returns {Object} - {id, title, slug} or {id, error}
 */
function convertAndSaveDoc(docId, folder) {
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

    // Save to Drive folder (overwrite if exists)
    var filename = slug + '.md';
    var existingFiles = folder.getFilesByName(filename);
    while (existingFiles.hasNext()) {
      existingFiles.next().setTrashed(true);
    }
    folder.createFile(filename, mdContent, MimeType.PLAIN_TEXT);

    return { id: docId, title: title, slug: slug };

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
    "created: " + created + "\n" +
    "type: " + type + "\n" +
    "source: " + source + "\n" +
    "source_id: " + id + "\n" +
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
