#!/usr/bin/env python3
"""Auth proxy in front of qmd's MCP endpoint (06 § 3, Q9: per-person login).

Context: members' agents reach the server's qmd over HTTP (plugin
.mcp.json, header `Authorization: Bearer <GitHub token>`). This proxy
accepts a request only if the token's user has read access to the brain
repo (GitHub `GET /repos/<repo>` succeeds), then forwards it unchanged to
qmd's local MCP server. Verdicts are cached for 5 minutes per token.
With one repo per tier later, the same check gives per-tier access.

Stdlib only. Run behind TLS (a reverse proxy such as caddy or nginx);
tokens must never travel in plain HTTP.

Environment
  BRAIN_REPO       repo whose read access grants search access    slds-lmu/wintermute-brain-content-slds
  QMD_UPSTREAM     qmd MCP server URL                              http://127.0.0.1:8182/mcp
  PROXY_PORT       listen port                                     8181

Usage: qmd-mcp-proxy.py
"""

from __future__ import annotations

import http.server
import os
import socketserver
import sys
import time
import urllib.error
import urllib.request

REPO = os.environ.get("BRAIN_REPO", "slds-lmu/wintermute-brain-content-slds")
UPSTREAM = os.environ.get("QMD_UPSTREAM", "http://127.0.0.1:8182/mcp").rstrip("/")
PORT = int(os.environ.get("PROXY_PORT", "8181"))
CACHE_TTL = 300
_cache: dict[str, tuple[bool, float]] = {}


def allowed(token: str) -> bool:
    hit = _cache.get(token)
    if hit and time.time() - hit[1] < CACHE_TTL:
        return hit[0]
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "brain-qmd-proxy"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError):
        ok = False
    _cache[token] = (ok, time.time())
    return ok


class Handler(http.server.BaseHTTPRequestHandler):
    def _forward(self):
        auth = self.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if not token or not allowed(token):
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"a GitHub token with read access to the brain repo is required\n")
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "authorization", "content-length")}
        req = urllib.request.Request(UPSTREAM + self.path[len("/mcp"):] if self.path.startswith("/mcp") else UPSTREAM, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(k, v)
                self.end_headers()
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            self.end_headers()
            self.wfile.write(exc.read())
        except urllib.error.URLError as exc:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"qmd unreachable: {exc.reason}\n".encode())

    do_GET = do_POST = do_DELETE = _forward

    def log_message(self, fmt, *args):  # quieter default log
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    print(f"qmd auth proxy on :{PORT} → {UPSTREAM}, access via read rights on {REPO}", flush=True)
    Server(("0.0.0.0", PORT), Handler).serve_forever()
