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
import sys
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote

from libs.common.config import extract_google_doc_id


# Apps Script Web App URL
PULL_URL = "https://script.google.com/a/macros/datadoghq.com/s/AKfycbxmAR6xY4t-_lfTTbTdoorihl-AgRGJPp5LyR3rCkfVQbaA1W0EPQPyEEx7D-zcs9nI6Q/exec"

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


def pull_doc(doc_id: str, output: str) -> None:
    """Pull a Google Doc as markdown to the specified output path."""
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


# --- CLI ---

def cmd_pull(args):
    """Pull a Google Doc as markdown."""
    doc_id = extract_google_doc_id(args.doc)
    if not doc_id:
        print(f"Error: Could not extract Google Doc ID from: {args.doc}", file=sys.stderr)
        sys.exit(1)

    pull_doc(doc_id, args.output)


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
