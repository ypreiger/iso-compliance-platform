#!/usr/bin/env python3
"""Minimal static server with /api proxy stub for OpenShift Route split later."""
from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

STATIC = Path(__file__).resolve().parent / "static"
API_URL = os.getenv("ISO_API_URL", "http://127.0.0.1:8080")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self):
        if self.path == "/api/health":
            try:
                with urlopen(f"{API_URL}/health", timeout=5) as resp:
                    body = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_error(502, "api unreachable")
            return
        if self.path in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"iso-web listening on {port}")
    server.serve_forever()
