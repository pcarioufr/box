#!/usr/bin/env python3
"""Google CLI - Pull Google Docs as local markdown.

Browser-based flow:
1. CLI starts a local HTTP server on a random port
2. CLI opens the Apps Script webhook URL in the browser with the doc ID
   and a callback URL pointing to the local server
3. Browser handles Google auth (restricted to "Only myself")
4. Apps Script converts the doc to markdown
5. Apps Script returns an HTML page with JS that POSTs the markdown
   content back to the local server
6. CLI receives the content and saves it to the output path
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote

from libs.common.config import extract_google_doc_id


# Apps Script Web App URL
PULL_URL = os.getenv("GOOGLE_DOCS_SYNC_URL", "")

# How long to wait for the callback (seconds)
CALLBACK_TIMEOUT = 120


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that receives markdown content from the browser."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        print(f"[callback] Received POST ({length} bytes)")
        body = self.rfile.read(length).decode("utf-8")

        try:
            data = json.loads(body)
            fname = data.get("filename", "?")
            content_len = len(data.get("content", ""))
            print(f"[callback] Parsed OK: filename={fname}, content={content_len} chars")
            self.server.result = data
        except json.JSONDecodeError:
            print(f"[callback] ERROR: Invalid JSON")
            self.server.result = {"error": "Invalid JSON received"}

        # Respond with a simple page so the browser tab shows completion
        response = (
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            "<title>Done</title>"
            '<style>body{font-family:system-ui,sans-serif;max-width:600px;'
            "margin:80px auto;text-align:center;color:#333}"
            "h1{color:#22863a}</style></head>"
            "<body><h1>Done</h1><p>You can close this tab.</p></body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response.encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        print("[callback] Received OPTIONS (CORS preflight)")
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logs


def _close_browser_tab(doc_id: str) -> None:
    """Try to close the browser tab via AppleScript (macOS only, silent fail)."""
    if sys.platform != "darwin":
        return
    # Match the tab by the doc ID in the URL (always present unencoded)
    needle = doc_id
    for app in ("Google Chrome", "Safari"):
        if app == "Google Chrome":
            script = f'''
            tell application "Google Chrome"
                repeat with w in windows
                    set tabList to tabs of w
                    repeat with i from (count of tabList) to 1 by -1
                        if URL of item i of tabList contains "{needle}" then
                            close item i of tabList
                        end if
                    end repeat
                end repeat
            end tell'''
        else:
            script = f'''
            tell application "Safari"
                repeat with w in windows
                    set tabList to tabs of w
                    repeat with i from (count of tabList) to 1 by -1
                        if URL of item i of tabList contains "{needle}" then
                            close item i of tabList
                        end if
                    end repeat
                end repeat
            end tell'''
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=3,
            )
        except Exception:
            pass


def pull_doc(doc_id: str, output: str) -> None:
    """Pull a Google Doc as markdown to the specified output path."""
    if not PULL_URL:
        print("GOOGLE_DOCS_SYNC_URL is not set. See env.example for setup.")
        sys.exit(1)
    output_path = Path(output)

    # Start local server on a random port
    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    server.result = None
    port = server.server_address[1]
    callback_url = f"http://localhost:{port}"

    # Run server in background thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Open browser with doc ID and callback URL
    url = f"{PULL_URL}?id={doc_id}&callback={quote(callback_url)}"
    print(f"Opening browser to convert doc {doc_id[:20]}...")
    print(f"[server] Listening on port {port}, callback={callback_url}")
    webbrowser.open(url)

    # Wait for the callback
    print("Waiting for response...")
    import time as _time
    deadline = _time.time() + CALLBACK_TIMEOUT
    last_log = 0
    while server.result is None and _time.time() < deadline:
        remaining = int(deadline - _time.time())
        if remaining != last_log and remaining % 10 == 0:
            print(f"[server] Still waiting... {remaining}s remaining")
            last_log = remaining
        _time.sleep(0.5)

    server.shutdown()
    if server.result is not None:
        print("[server] Got result, shutting down")
        _close_browser_tab(doc_id)

    if server.result is None:
        print(f"\nNo response received within {CALLBACK_TIMEOUT}s.")
        print("Check browser for errors, then retry.")
        sys.exit(1)

    result = server.result

    if "error" in result:
        print(f"\nError from Apps Script: {result['error']}", file=sys.stderr)
        sys.exit(1)

    content = result.get("content", "")
    filename = result.get("filename", "document.md")

    if not content:
        print("Error: Empty content received.", file=sys.stderr)
        sys.exit(1)

    # Ensure google_id in frontmatter
    content = ensure_google_id(content, doc_id)

    # Resolve output path
    if output_path.is_dir() or output.endswith("/"):
        output_path.mkdir(parents=True, exist_ok=True)
        output_path = output_path / filename
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(content, encoding="utf-8")
    print(f"Saved to {output_path}")


def ensure_google_id(content: str, doc_id: str) -> str:
    """Ensure the markdown has google_id in its YAML frontmatter."""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            frontmatter = content[3:end]
            if f"google_id: {doc_id}" in frontmatter:
                return content
            if "google_id:" not in frontmatter:
                content = content[:3] + frontmatter.rstrip() + f"\ngoogle_id: {doc_id}\n" + content[end:]
            return content

    # No frontmatter — add one
    return f"---\ngoogle_id: {doc_id}\n---\n\n{content}"


def find_google_docs(directory: str) -> list[tuple[Path, str]]:
    """Scan directory recursively for .md files with google_id in frontmatter.

    Returns list of (file_path, google_id) tuples.
    """
    import re
    results = []
    for md_file in Path(directory).rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not text.startswith("---"):
            continue
        end = text.find("---", 3)
        if end == -1:
            continue
        frontmatter = text[3:end]
        match = re.search(r'^google_id:\s*(.+)$', frontmatter, re.MULTILINE)
        if match:
            doc_id = match.group(1).strip().strip('"').strip("'")
            results.append((md_file, doc_id))
    return results


# --- CLI ---

def cmd_pull(args):
    """Pull a Google Doc as markdown."""
    doc_id = extract_google_doc_id(args.doc)
    if not doc_id:
        print(f"Error: Could not extract Google Doc ID from: {args.doc}", file=sys.stderr)
        sys.exit(1)

    pull_doc(doc_id, args.output)


def cmd_pull_all(args):
    """Re-pull all Google Docs found in a directory."""
    directory = args.directory
    if not Path(directory).is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    docs = find_google_docs(directory)
    if not docs:
        print(f"No files with google_id frontmatter found in {directory}")
        return

    print(f"Found {len(docs)} Google Doc(s) to refresh:")
    for path, doc_id in docs:
        print(f"  {path} ({doc_id[:20]}...)")
    print()

    succeeded = 0
    failed = 0
    for path, doc_id in docs:
        print(f"Pulling {path.name}...")
        try:
            pull_doc(doc_id, str(path))
            succeeded += 1
        except SystemExit:
            failed += 1
            print(f"  Failed, skipping.")
        except Exception as e:
            failed += 1
            print(f"  Error: {e}")
        print()

    print(f"Done: {succeeded} succeeded, {failed} failed")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="google",
        description="Google CLI - Pull Google Docs as local markdown",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Pull command
    pull_parser = subparsers.add_parser("pull", help="Pull a Google Doc as markdown")
    pull_parser.add_argument("doc", help="Google Doc URL or ID")
    pull_parser.add_argument("-o", "--output", default=".", help="Output file path (.md) or directory (default: current dir)")
    pull_parser.set_defaults(func=cmd_pull)

    # Pull-all command
    pull_all_parser = subparsers.add_parser(
        "pull-all",
        help="Re-pull all Google Docs in a directory",
        description="""Scan a directory recursively for .md files with google_id
in their YAML frontmatter, and re-pull each one from Google Docs.

Each file is updated in place. Requires browser auth for each doc
(one browser tab per doc, sequentially).

EXAMPLES:
  google pull-all data/project/
  google pull-all .
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pull_all_parser.add_argument("directory", help="Directory to scan for Google Docs")
    pull_all_parser.set_defaults(func=cmd_pull_all)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
