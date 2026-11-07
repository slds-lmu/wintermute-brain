"""Renew GitHub App tokens for git and gh without restarting the worker."""

from __future__ import annotations

import base64
import fcntl
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def mint_token() -> dict:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "iat": now - 60, "exp": now + 540, "iss": os.environ["BRAIN_APP_ID"],
    }).encode())
    signing = f"{header}.{payload}".encode()
    signature = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", os.environ["BRAIN_APP_KEY"]],
        input=signing, capture_output=True, check=True,
    ).stdout
    request = urllib.request.Request(
        "https://api.github.com/app/installations/"
        + os.environ["BRAIN_APP_INSTALLATION_ID"] + "/access_tokens",
        method="POST",
        headers={
            "Authorization": f"Bearer {signing.decode()}.{_b64(signature)}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "wintermute-brain",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_token() -> str:
    directory = Path(os.environ.get("BRAIN_AUTH_CACHE", "/state/auth"))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    cache = directory / "installation-token.json"
    with open(directory / "token.lock", "a", opener=_private_open) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            value = json.loads(cache.read_text())
            expires = datetime.fromisoformat(value["expires_at"].replace("Z", "+00:00")).timestamp()
            if expires - time.time() > 300:
                return value["token"]
        except (OSError, ValueError, KeyError):
            pass
        value = mint_token()
        temporary = cache.with_suffix(".tmp")
        with open(temporary, "w", opener=_private_open) as handle:
            json.dump(value, handle)
        temporary.replace(cache)
        return value["token"]


def _private_open(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)


def credential() -> None:
    if len(sys.argv) < 2 or sys.argv[1] != "get":
        return
    fields = dict(line.rstrip("\n").split("=", 1) for line in sys.stdin if "=" in line)
    repos = {
        os.environ.get("BRAIN_REPO", "slds-lmu/wintermute-brain-content-slds"),
        os.environ.get("BRAIN_CODE_REPO", "slds-lmu/wintermute-brain"),
    }
    if fields.get("protocol") == "https" and fields.get("host") == "github.com":
        path = fields.get("path", "")
        if not any(
            path in {repo, repo + ".git"} or path.startswith(repo + ".git/info/lfs")
            for repo in repos
        ):
            return
        print("username=x-access-token")
        print("password=" + get_token())


def gh() -> None:
    os.environ["GH_TOKEN"] = get_token()
    os.execv("/usr/bin/gh", ["gh", *sys.argv[1:]])
