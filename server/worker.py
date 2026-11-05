#!/usr/bin/env python3
"""The brain's compile worker (02 § 2.4, 06 § 4). Runs on the group server.

Every POLL seconds: pull main, compile raw items that have no summary page
(one at a time, each in its own worktree with a `claude -p` run that
follows the brain skill and commits via tools/commit-op), then re-index
qmd. The queue is derived (raw items without a summary page); the only
local state is a backoff file for items that keep failing, which is a
cache and may be deleted.

Code and content are separate repos (01 § 1): BRAIN_DIR is a clone of
the content repo; BRAIN_CODE_DIR a clone of the code repo, which the
worker checks out at the tag pinned in the content's `.brain-version`
before every cycle, so CI, members and the server run the same code.

Environment
  BRAIN_DIR        clone of the content repo (full LFS fetch)      required
  BRAIN_CODE_DIR   clone of the code repo (slds-lmu/wintermute-brain) required
  BRAIN_REPO       GitHub repo slug of the content               slds-lmu/wintermute-brain-content-slds
  BRAIN_MODEL      model for the compile agent                    sonnet
  BRAIN_POLL       seconds between polls                          300
  BRAIN_MAX_TRIES  attempts per item before reporting + 24 h backoff   3
  BRAIN_QMD        qmd command to re-index after a pull, "" = none     qmd update
  ANTHROPIC_API_KEY  group API key with a spending limit (06 § 5)
  GH_TOKEN         GitHub App installation token (server/github-app-token.py)

Usage: worker.py [--once] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

BRAIN_DIR = Path(os.environ.get("BRAIN_DIR", "/brain/repo")).expanduser()
CODE_DIR = Path(os.environ.get("BRAIN_CODE_DIR", "/brain/code")).expanduser()
CODE_REPO = os.environ.get("BRAIN_CODE_REPO", "slds-lmu/wintermute-brain")
REPO = os.environ.get("BRAIN_REPO", "slds-lmu/wintermute-brain-content-slds")
PLUGIN_DIR = CODE_DIR / "plugin"
TOOLS = PLUGIN_DIR / "tools"
MODEL = os.environ.get("BRAIN_MODEL", "sonnet")
POLL = int(os.environ.get("BRAIN_POLL", "300"))
MAX_TRIES = int(os.environ.get("BRAIN_MAX_TRIES", "3"))
QMD = os.environ.get("BRAIN_QMD", "")
AGENT = "brain-agent-compile"
STATE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "brain-worker" / "backoff.json"
BACKOFF = 24 * 3600


def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def sh(cmd: list[str], cwd: Path | None = None, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1))


def pull() -> bool:
    r = sh(["git", "pull", "--ff-only", "--quiet", "origin", "main"], BRAIN_DIR)
    if r.returncode != 0:
        log(f"pull failed: {r.stderr.strip()[:300]}")
        return False
    return True


def sync_code() -> bool:
    """Check out the code repo at the tag pinned in the content's
    .brain-version (01 § 1)."""
    try:
        version = (BRAIN_DIR / ".brain-version").read_text().strip()
    except OSError:
        log("content repo has no .brain-version")
        return False
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", version):
        log("content .brain-version must name a release tag")
        return False
    ref = "refs/tags/" + version
    fetched = sh(["git", "fetch", "--quiet", "--depth=1", "origin", ref + ":" + ref], CODE_DIR)
    if fetched.returncode:
        log(f"cannot fetch code version {version}: {fetched.stderr.strip()[:300]}")
        return False
    r = sh(["git", "checkout", "--quiet", "--detach", ref], CODE_DIR)
    if r.returncode != 0:
        log(f"cannot check out code version {version}: {r.stderr.strip()[:300]}")
        return False
    return True


def queue() -> list[str]:
    r = sh([sys.executable, str(TOOLS / "check_evidence"), "--queue"], BRAIN_DIR)
    if r.returncode:
        raise RuntimeError("compile queue check failed: " + r.stderr.strip()[:300])
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


def report_health(title: str, body: str) -> None:
    sh([sys.executable, str(TOOLS / "report-health"), "--repo", REPO, "--title", title,
        "--agent", AGENT, "--body", body], BRAIN_DIR)


def compile_item(item: str, dry_run: bool) -> bool:
    """One attempt: worktree → claude -p (skill + commit-op) → verify merge."""
    r = sh([sys.executable, str(TOOLS / "start-op"), "--agent", AGENT], BRAIN_DIR)
    if r.returncode != 0:
        log(f"start-op failed: {r.stderr.strip()[:300]}")
        return False
    wt = Path(r.stdout.strip())
    try:
        prompt = f"Compile the raw item `{item}` (folder in this worktree). Follow the compile instructions."
        cmd = [
            "claude", "-p", "--model", MODEL, "--dangerously-skip-permissions",
            "--no-session-persistence", "--output-format", "json",
            "--plugin-dir", str(PLUGIN_DIR),
            "--append-system-prompt-file", str(CODE_DIR / "server" / "compile-prompt.md"),
            prompt,
        ]
        if dry_run:
            log("dry run: " + " ".join(shlex.quote(c) for c in cmd))
            return True
        env = dict(os.environ, BRAIN_DIR=str(BRAIN_DIR), BRAIN_REPO=REPO, BRAIN_TOOLS=str(TOOLS),
                   BRAIN_SESSION_DIGEST="off")
        r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, env=env, timeout=3600)
        log(f"agent finished ({r.returncode})")
        # Success = the summary page exists on main now.
        pull()
        return queue().count(item) == 0
    except subprocess.TimeoutExpired:
        log("agent timed out")
        return False
    finally:
        sh([sys.executable, str(TOOLS / "start-op"), "--discard", str(wt)], BRAIN_DIR)


def reindex() -> None:
    if not QMD:
        return
    r = sh(shlex.split(QMD), BRAIN_DIR)
    if r.returncode != 0:
        log(f"qmd re-index failed: {r.stderr.strip()[:300]}")


def cycle(dry_run: bool) -> None:
    if not pull():
        return
    (BRAIN_DIR / ".git" / "brain-ready").write_text(str(time.time()))
    if not sync_code():
        return
    state = load_state()
    now = time.time()
    for item in queue():
        if os.environ.get("BRAIN_AUTO_COMPILE", "true").lower() != "true":
            break
        entry = state.get(item, {"tries": 0, "until": 0})
        if entry.get("until", 0) > now:
            continue
        log(f"compiling {item} (try {entry['tries'] + 1}/{MAX_TRIES})")
        if compile_item(item, dry_run):
            state.pop(item, None)
            log(f"done {item}")
        else:
            entry["tries"] += 1
            if entry["tries"] >= MAX_TRIES:
                report_health(f"compile failed: {item}", f"gave up after {MAX_TRIES} attempts; retrying in 24 h. See the worker log on the server.")
                entry = {"tries": 0, "until": now + BACKOFF}
            state[item] = entry
        save_state(state)
    reindex()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print the agent command instead of running it")
    args = ap.parse_args(argv)
    while True:
        try:
            if not (BRAIN_DIR / ".git").exists():
                BRAIN_DIR.parent.mkdir(parents=True, exist_ok=True)
                result = sh(["git", "clone", "https://github.com/" + REPO + ".git", str(BRAIN_DIR)])
                if result.returncode:
                    raise RuntimeError("initial content clone failed: " + result.stderr.strip()[-300:])
            if not (CODE_DIR / ".git").exists():
                CODE_DIR.mkdir(parents=True, exist_ok=True)
                sh(["git", "init", "--quiet"], CODE_DIR, check=True)
                sh(["git", "remote", "add", "origin", "https://github.com/" + CODE_REPO + ".git"], CODE_DIR, check=True)
            cycle(args.dry_run)
        except Exception as exc:  # noqa: BLE001 - the loop must survive
            log(f"cycle failed: {exc}")
        if args.once:
            return 0
        time.sleep(POLL)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
