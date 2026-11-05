#!/usr/bin/env python3
"""Mint a short-lived installation token for the brain's GitHub App (06 § 4).

Context: the server worker pushes PRs and comments on the "Brain health"
issue as a GitHub App installed on the brain repo only (no seat). This
prints a token valid for one hour; the systemd unit runs it before each
worker start (see brain-worker.service) and the worker reads it from
GH_TOKEN. Stdlib + the openssl CLI; no Python dependencies.

Environment
  BRAIN_APP_ID               the App's id
  BRAIN_APP_INSTALLATION_ID  the installation id on the brain repo
  BRAIN_APP_KEY              path to the App's private key (PEM)
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.request


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> int:
    app_id = os.environ["BRAIN_APP_ID"]
    inst = os.environ["BRAIN_APP_INSTALLATION_ID"]
    key = os.environ["BRAIN_APP_KEY"]
    now = int(time.time())
    header = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = b64(json.dumps({"iat": now - 60, "exp": now + 540, "iss": app_id}).encode())
    signing = f"{header}.{payload}".encode()
    sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", key], input=signing, capture_output=True, check=True).stdout
    jwt = f"{header}.{payload}.{b64(sig)}"
    req = urllib.request.Request(
        f"https://api.github.com/app/installations/{inst}/access_tokens",
        method="POST",
        headers={"Authorization": f"Bearer {jwt}", "Accept": "application/vnd.github+json", "User-Agent": "brain-worker"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(json.load(resp)["token"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
