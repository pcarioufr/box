
Folder highlights
Google Apps Script converts docs to markdown via a webhook, last updated by @pierre.cariou on Jan 26, 2026.

# Webhook Setup Guide for docdown.gs

This guide explains how to deploy the Google Docs to Markdown script as a webhook that can be triggered via browser.

**Output format:** Google Docs are converted to markdown files with the same name + .md extension (e.g., "My Document" → "My Document.md")

---

## Step 1: (Optional) Generate a Webhook Token

If you want to add token-based security, generate a secure random token:

**Option A - Command line:**
```bash
openssl rand -hex 32
```

**Option B - Online generator:**
- Visit: https://www.random.org/strings/ or https://1password.com/password-generator/
- Generate a long random string (at least 32 characters)

**Example token:** `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6`

**Note:** Token authentication is optional. If you leave `WEBHOOK_TOKEN` empty in CONFIG, the webhook will work without token validation.

---

## Step 2: (Optional) Configure the Script

1. Open your Google Apps Script project
2. Find the `CONFIG` object at the top
3. Set the `WEBHOOK_TOKEN` value (or leave empty to disable):

```javascript
WEBHOOK_TOKEN: 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6'
```

4. Save the script (Ctrl+S or Cmd+S)

---

## Step 3: Deploy as Web App

1. In Google Apps Script, click **Deploy** → **New deployment**
2. Click the gear icon ⚙️ next to "Select type" → Choose **Web app**
3. Fill in the settings:
   - **Description:** "GDoc to Markdown Webhook v1"
   - **Execute as:** Me (your-email@datadoghq.com) ⚠️ IMPORTANT
   - **Who has access:** Anyone ⚠️ IMPORTANT
4. Click **Deploy**
5. Review permissions if prompted and authorize
6. **Copy the Web app URL** - it looks like:
   ```
   https://script.google.com/macros/s/AKfycbz.../exec
   ```
7. Keep this URL safe - you'll need it to trigger the webhook

**⚠️ Common Issue: "Execute as" must be "Me"**

If you see HTTP 302 redirects or authentication errors, it means the deployment is configured incorrectly. The script MUST be set to:
- **Execute as: Me (your account)** - NOT "User accessing the web app"
- **Who has access: Anyone** - This allows unauthenticated access (token provides security)

If you deployed with wrong settings, go to Deploy → Manage deployments → Edit → Fix settings → Deploy

---

## Step 4: Test the Webhook

Run the sync script, which will open your browser:

```bash
./libs/sync-gdocs.sh
```

Your browser will open and you'll see a JSON response:

**Expected response (success):**
```json
{
  "success": true,
  "message": "Sync completed successfully",
  "timestamp": "2026-01-26T12:34:56.789Z"
}
```

**Expected response (unauthorized - if token is required but missing/wrong):**
```json
{
  "success": false,
  "error": "Unauthorized: Invalid or missing token"
}
```

---

## Step 5: Daily Usage

To trigger a sync anytime:

```bash
./libs/sync-gdocs.sh
```

Your browser will open, handle authentication automatically, and show the sync result.

---

## Security Notes

- **Keep your token secret** (if using token authentication) - anyone with the token can trigger syncs
- The webhook URL can be public, but the token should not be
- You can regenerate the token anytime by updating CONFIG and redeploying
- To redeploy: Deploy → Manage deployments → Edit → New version → Deploy
- The browser-based approach leverages your existing Google authentication

---

## Troubleshooting

**"Unauthorized" error in browser:**
- If using token authentication: Check that GDOC_WEBHOOK_TOKEN environment variable matches CONFIG
- Verify WEBHOOK_TOKEN is set correctly in CONFIG (or empty if not using tokens)

**"Script has not been published" error:**
- Make sure "Who has access" is set to "Anyone" in deployment settings

**No response or browser shows error:**
- Check Google Apps Script logs: View → Executions
- Verify the script runs manually first in Google Apps Script editor

**Permission errors:**
- Re-authorize the script: Deploy → Manage deployments → Re-authorize

---

## (Optional) Store Token Safely

If using token authentication, you can store it as an environment variable:

```bash
# Add to ~/.bashrc or ~/.zshrc
export GDOC_WEBHOOK_TOKEN="your-secret-token"
```

Then the sync-gdocs.sh script will automatically include it.

---

**Last Updated:** 2026-01-26