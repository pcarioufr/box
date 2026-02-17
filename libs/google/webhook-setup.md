
Folder highlights
Google Apps Script converts docs to markdown via a webhook, last updated by @pierre.cariou on Jan 26, 2026.

# Webhook Setup Guide for docdown.gs

This guide explains how to deploy the Google Docs to Markdown script as a webhook that can be triggered via browser.

**Output format:** Google Docs are converted to markdown files with the same name + .md extension (e.g., "My Document" → "My Document.md")

---

## Step 1: Configure the Script (No Token)

1. Open your Google Apps Script project
2. Find the `CONFIG` object at the top
3. Set the `WEBHOOK_TOKEN` to empty (disable token authentication):

```javascript
WEBHOOK_TOKEN: ''
```

4. Save the script (Ctrl+S or Cmd+S)

**Note:** Token authentication is NOT used. Security is provided by restricting the API to only your Google account via browser authentication.

---

## Step 2: Deploy as Web App

1. In Google Apps Script, click **Deploy** → **New deployment**
2. Click the gear icon ⚙️ next to "Select type" → Choose **Web app**
3. Fill in the settings:
   - **Description:** "GDoc to Markdown Webhook v1"
   - **Execute as:** Me (your-email@datadoghq.com) ⚠️ IMPORTANT
   - **Who has access:** Only myself ⚠️ IMPORTANT
4. Click **Deploy**
5. Review permissions if prompted and authorize
6. **Copy the Web app URL** - it looks like:
   ```
   https://script.google.com/macros/s/AKfycbz.../exec
   ```
7. Keep this URL - you'll need it to trigger the webhook

**⚠️ Important Settings**

The script MUST be configured as:
- **Execute as: Me (your account)** - NOT "User accessing the web app"
- **Who has access: Only myself** - This restricts access to only your Google account (org policy may not allow "Anyone")

When you access the webhook URL in your browser, you'll be prompted to authenticate with your Google account if not already logged in. This provides security without requiring token authentication.

If you deployed with wrong settings, go to Deploy → Manage deployments → Edit → Fix settings → Deploy

---

## Step 3: Test the Webhook

Run the sync script, which will open your browser:

```bash
./box.sh google refresh
```

Your browser will open and handle authentication automatically:

**Expected response (success):**
```json
{
  "success": true,
  "message": "Sync completed successfully",
  "timestamp": "2026-01-26T12:34:56.789Z"
}
```

**Expected response (authentication required):**
- If not logged into Google, you'll see a Google sign-in page
- After signing in, you'll be redirected to the success response above

---

## Step 4: Daily Usage

To trigger a sync anytime:

```bash
./box.sh google refresh
```

Your browser will open, handle authentication automatically via your Google session, and show the sync result.

---

## Security Notes

- **Access control:** The webhook is restricted to your Google account only ("Only myself" setting)
- **No token required:** Security is provided by Google's browser-based authentication
- **Private by default:** Only you can access the webhook when signed into your Google account
- The browser-based approach leverages your existing Google session for authentication
- To redeploy: Deploy → Manage deployments → Edit → New version → Deploy

---

## Troubleshooting

**"Sign in required" page:**
- This is normal if you're not logged into Google
- Sign in with your Google account and you'll be redirected to the webhook

**"Authorization required" or permissions prompt:**
- Review and accept the permissions
- This happens on first use or after redeployment

**"Script has not been published" error:**
- Make sure "Who has access" is set to "Only myself" in deployment settings
- Verify "Execute as" is set to "Me"

**No response or browser shows error:**
- Check Google Apps Script logs: View → Executions
- Verify the script runs manually first in Google Apps Script editor

**Permission errors:**
- Re-authorize the script: Deploy → Manage deployments → Re-authorize

---

**Last Updated:** 2026-01-26