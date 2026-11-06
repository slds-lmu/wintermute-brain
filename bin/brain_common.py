"""Shared helpers for `setup-brain` and `brain` (06 § 2.1).

The member's settings live in one file, ~/.config/brain/config.toml:

    person      = "jane-doe"
    repo        = "slds-lmu/wintermute-brain-content-slds"
    dir         = "~/brain/wintermute-brain-content-slds"
    code_dir    = "~/.local/share/brain/code"
    login       = "gh"            # or "token"
    token_file  = ""              # login = "token": file holding the token
    search_url  = ""              # the search server; empty = the group's server
    capture     = ["~/brain/wintermute-brain-content-slds"]

`brain` turns it into the environment the plugin and the tools read
(BRAIN_DIR, BRAIN_REPO, BRAIN_PERSON, BRAIN_QMD_URL, BRAIN_CAPTURE,
BRAIN_GITHUB_TOKEN and, in token mode, GH_TOKEN), for one Claude Code
session only.
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = Path(os.environ.get("BRAIN_CONFIG", "~/.config/brain/config.toml")).expanduser()
DEFAULT_REPO = "slds-lmu/wintermute-brain-content-slds"
CODE_REPO = "slds-lmu/wintermute-brain"
DEFAULT_SEARCH_URL = "https://api.wintermute-gpu.stat.uni-muenchen.de/brain/mcp"


def expand(p: str) -> Path:
    return Path(os.path.expandvars(p)).expanduser()


def load_config(path: Path = CONFIG) -> dict:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        sys.exit("brain needs Python 3.11 or newer (tomllib).")
    if not path.is_file():
        sys.exit(f"no brain config at {path}; run setup-brain first.")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def toml_value(v) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(toml_value(x) for x in v) + "]"
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def write_config(cfg: dict, path: Path = CONFIG) -> None:
    order = ["person", "repo", "dir", "code_dir", "login", "token_file", "search_url", "capture"]
    lines = ["# Brain settings for this member (06 § 2.1). Written by setup-brain; edit freely."]
    for k in order + [k for k in cfg if k not in order]:
        if k in cfg:
            lines.append(f"{k} = {toml_value(cfg[k])}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def session_env(cfg: dict, base: dict | None = None) -> dict:
    """Environment for one brain session, derived from the config."""
    env = dict(os.environ if base is None else base)
    env["BRAIN_DIR"] = str(expand(cfg["dir"]))
    env["BRAIN_REPO"] = cfg.get("repo", DEFAULT_REPO)
    env["BRAIN_PERSON"] = cfg.get("person", "")
    env["BRAIN_QMD_URL"] = cfg.get("search_url") or DEFAULT_SEARCH_URL
    env["BRAIN_CAPTURE"] = os.pathsep.join(str(expand(p)) for p in cfg.get("capture", []))
    if cfg.get("login") == "token":
        tok = expand(cfg.get("token_file", "")).read_text().strip()
        env["GH_TOKEN"] = tok
        env["GITHUB_TOKEN"] = tok
    else:
        tok = gh_token(env)
    # The plugin's connection to the search server needs the token itself. A member
    # may have exported a narrower one for this.
    if tok:
        env.setdefault("BRAIN_GITHUB_TOKEN", tok)
    return env


def gh_token(env: dict) -> str:
    try:
        r = subprocess.run(["gh", "auth", "token"], env=env, capture_output=True, text=True)
    except OSError:
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def search_status(url: str, token: str) -> int | None:
    """HTTP status of a request the search server rejects only after the login.

    405: the login was accepted. 401: it was not. None: no answer. Others: unclear.
    """
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (OSError, ValueError):
        return None
