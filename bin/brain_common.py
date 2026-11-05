"""Shared helpers for `setup-brain` and `brain` (06 § 2.1).

The member's settings live in one file, ~/.config/brain/config.toml:

    person      = "jane-doe"
    repo        = "slds-lmu/wintermute-brain-content-slds"
    dir         = "~/brain/wintermute-brain-content-slds"
    code_dir    = "~/.local/share/brain/code"
    login       = "gh"            # or "token"
    token_file  = ""              # login = "token": file holding the token
    search_url  = ""              # the server's qmd MCP endpoint, if any
    capture     = ["~/brain/wintermute-brain-content-slds"]

`brain` turns it into the environment the plugin and the tools read
(BRAIN_DIR, BRAIN_REPO, BRAIN_PERSON, BRAIN_QMD_URL, BRAIN_CAPTURE and,
in token mode, GH_TOKEN), for one Claude Code session only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

CONFIG = Path(os.environ.get("BRAIN_CONFIG", "~/.config/brain/config.toml")).expanduser()
DEFAULT_REPO = "slds-lmu/wintermute-brain-content-slds"
CODE_REPO = "slds-lmu/wintermute-brain"


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
    if cfg.get("search_url"):
        env["BRAIN_QMD_URL"] = cfg["search_url"]
    env["BRAIN_CAPTURE"] = os.pathsep.join(str(expand(p)) for p in cfg.get("capture", []))
    if cfg.get("login") == "token":
        tok = expand(cfg.get("token_file", "")).read_text().strip()
        env["GH_TOKEN"] = tok
        env["GITHUB_TOKEN"] = tok
    return env
