#!/usr/bin/env python3
"""Session-digest channel for the brain (02 § 2): make digests of Claude
Code work sessions and open raw-only PRs on the brain repo.

Context: called by scripts/brain-session.sh from the Stop, SessionStart
and SessionEnd hooks with the hook JSON on stdin. The hook call only
decides whether there is enough new material and forks the real work
(`digest` sub-command) into the background. Nothing here touches wiki/;
the server-side compile worker turns raw digests into pages.

Checkpoint without local state: each digest's source.yaml records the
session id and the message range it covers, so "where did I stop" can be
derived from the brain repo. A per-session cache file speeds this up; it
is a cache, losing it is harmless.

Environment
  BRAIN_REPO           GitHub repo, default slds-lmu/wintermute-brain-content-slds
  BRAIN_PERSON         person slug (first-last); default from git user.name
  BRAIN_DIGEST_MODEL   model for the digest agent, default haiku (02 I3)
  BRAIN_DIGEST_TURNS   new human turns that trigger a digest, default 20 (02 I2)
  BRAIN_DIGEST_MINUTES minutes since the last digest that trigger one, default 30
  BRAIN_SESSION_DIGEST set to "off" to disable the channel
  BRAIN_CAPTURE        folders whose sessions are captured (path list; set by
                       `brain` from ~/.config/brain/config.toml). Unset = none
Needs: claude (CLI), gh (logged in), gitleaks (recommended, R15).
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
def _member_config() -> dict:
    """The member's settings file (06 § 2.1) takes precedence over the
    environment: shell startup files (e.g. ~/.zshenv) can silently
    override variables that `brain` sets (user test N22)."""
    path = Path(os.environ.get("BRAIN_CONFIG", "~/.config/brain/config.toml")).expanduser()
    try:
        import tomllib
        return tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except Exception:  # noqa: BLE001 - a broken config must not break the hook
        return {}


CFG = _member_config()
REPO = CFG.get("repo") or os.environ.get("BRAIN_REPO", "slds-lmu/wintermute-brain-content-slds")
MODEL = os.environ.get("BRAIN_DIGEST_MODEL", "haiku")
TURNS = int(os.environ.get("BRAIN_DIGEST_TURNS", "20"))
MINUTES = int(os.environ.get("BRAIN_DIGEST_MINUTES", "30"))
MIN_TURNS_FLUSH = 3            # a flush at session end/start needs at least this much
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "brain"
LOG = CACHE / "digest.log"
NOTICE = ("Brain: this session is captured into {repo} (decisions, findings, failed approaches, "
          "open questions; names included). Off for one session: BRAIN_SESSION_DIGEST=off.")
AGENT = "brain-agent-digest"
AGENT_EMAIL = "brain-agent-digest@agents.invalid"
MAX_CHARS = 120_000            # transcript budget handed to the digest model
SECRET_PATTERNS = [            # fallback when gitleaks is missing
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+]{16,}"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def log(msg: str) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}\n")


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# --- transcript ----------------------------------------------------------------


def read_transcript(path: Path) -> list[dict]:
    """Conversation records (user/assistant, main thread) in file order."""
    out = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") in ("user", "assistant") and not rec.get("isSidechain") and not rec.get("isMeta"):
                    out.append(rec)
    except OSError:
        pass
    return out


def is_human_turn(rec: dict) -> bool:
    if rec.get("type") != "user":
        return False
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(b.get("type") == "text" for b in content if isinstance(b, dict))
    return False


def render(records: list[dict], start: int, end: int) -> str:
    """Readable text of messages start..end (1-based, inclusive)."""
    parts = []
    for i in range(start - 1, min(end, len(records))):
        rec = records[i]
        role = rec.get("type")
        content = (rec.get("message") or {}).get("content")
        chunks = []
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                t = b.get("type")
                if t == "text":
                    chunks.append(b.get("text", ""))
                elif t == "tool_use":
                    inp = json.dumps(b.get("input", {}))[:300]
                    chunks.append(f"[tool {b.get('name')}] {inp}")
                elif t == "tool_result":
                    c = b.get("content")
                    text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                    chunks.append(f"[result] {text[:500]}")
        text = "\n".join(c for c in chunks if c).strip()
        if text:
            parts.append(f"### {i + 1} {role}\n{text}")
    text = "\n\n".join(parts)
    if len(text) > MAX_CHARS:  # keep head and tail, note the cut
        half = MAX_CHARS // 2
        text = text[:half] + "\n\n[… transcript cut for length …]\n\n" + text[-half:]
    return text


def project_transcripts(cwd: str) -> list[Path]:
    """All transcripts of this project directory, as Claude Code stores them."""
    encoded = re.sub(r"[^A-Za-z0-9]", "-", cwd)
    d = Path.home() / ".claude" / "projects" / encoded
    return sorted(d.glob("*.jsonl")) if d.is_dir() else []


# --- checkpoints ---------------------------------------------------------------


def cache_file(session_id: str) -> Path:
    return CACHE / "sessions" / f"{session_id}.json"


def load_cache(session_id: str) -> dict:
    p = cache_file(session_id)
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(session_id: str, data: dict) -> None:
    p = cache_file(session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))


def digested_until_from_repo(session_id: str, limit: int = 150) -> int:
    """Derive the checkpoint from raw/session/ in the brain repo: the highest
    message index any digest of this session covers. Reads the newest
    `limit` session items (ids sort by date)."""
    r = sh(["gh", "api", f"repos/{REPO}/git/trees/main?recursive=1", "--jq",
            '.tree[] | select(.path | test("^raw/session/[0-9]{4}/[^/]+/source.yaml$")) | .path'])
    if r.returncode != 0:
        log(f"gh tree failed: {r.stderr.strip()[:200]}")
        return 0
    paths = sorted(r.stdout.split(), key=lambda p: p.split("/")[3], reverse=True)[:limit]
    best = 0
    for path in paths:
        c = sh(["gh", "api", f"repos/{REPO}/contents/{path}", "--jq", ".content"])
        if c.returncode != 0:
            continue
        try:
            text = base64.b64decode(c.stdout.strip()).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            continue
        if f"session: {session_id}" not in text:
            continue
        m = re.search(r"messages:\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]", text)
        if m:
            best = max(best, int(m.group(2)))
    return best


def checkpoint(session_id: str) -> dict:
    data = load_cache(session_id)
    if "digested_until" not in data:
        data["digested_until"] = digested_until_from_repo(session_id)
        data["last_digest_at"] = time.time()
        save_cache(session_id, data)
    return data


# --- deciding and forking ------------------------------------------------------


def spawn_digest(transcript: Path, session_id: str, cwd: str, start: int, end: int) -> None:
    data = load_cache(session_id)
    pending = data.get("pending")
    if pending and time.time() - pending.get("at", 0) < 3600:
        return  # a digest for this session is already running
    data["pending"] = {"at": time.time(), "end": end}
    save_cache(session_id, data)
    env = dict(os.environ, BRAIN_DIGEST_CHILD="1")
    CACHE.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as out:
        subprocess.Popen(
            [sys.executable, str(HERE / "brain_session.py"), "digest", str(transcript), session_id, cwd, str(start), str(end)],
            stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True, env=env,
        )
    log(f"spawned digest {session_id} {start}-{end}")


def consider(transcript: Path, session_id: str, cwd: str, flush: bool) -> None:
    records = read_transcript(transcript)
    total = len(records)
    cp = checkpoint(session_id)
    done = int(cp.get("digested_until", 0))
    if total <= done:
        return
    new_turns = sum(1 for r in records[done:] if is_human_turn(r))
    minutes = (time.time() - cp.get("last_digest_at", 0)) / 60
    if flush:
        if new_turns >= MIN_TURNS_FLUSH:
            spawn_digest(transcript, session_id, cwd, done + 1, total)
    elif new_turns >= TURNS or (minutes >= MINUTES and new_turns >= MIN_TURNS_FLUSH):
        spawn_digest(transcript, session_id, cwd, done + 1, total)


def captured(cwd: str) -> bool:
    """Only sessions in folders listed in BRAIN_CAPTURE (set by `brain` from
    the member's config, 06 § 2.1), or below them, are captured. Without
    the list nothing is captured (user test N6: with --plugin-dir every
    session was)."""
    if "capture" in CFG:
        listed = [str(p) for p in CFG.get("capture") or []]
    else:
        listed = [p for p in os.environ.get("BRAIN_CAPTURE", "").split(os.pathsep) if p]
    try:
        here = Path(cwd).resolve()
    except OSError:
        return False
    for p in listed:
        try:
            root = Path(p).expanduser().resolve()
        except OSError:
            continue
        if here == root or root in here.parents:
            return True
    return False


def hook(event: str) -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return
    session_id = payload.get("session_id") or ""
    transcript = Path(payload.get("transcript_path") or "")
    cwd = payload.get("cwd") or os.getcwd()
    if not captured(cwd):
        return  # not a captured folder: no digest, no notice (06 § 2.1)
    if event in ("stop", "end"):
        if transcript.is_file() and session_id:
            consider(transcript, session_id, cwd, flush=(event == "end"))
    elif event == "start":
        # Tell the person that this session is captured (06 § 7a, PD3). Claude
        # Code shows a hook's `systemMessage` to the user.
        print(json.dumps({"systemMessage": NOTICE.format(repo=REPO)}), flush=True)
        # Older sessions of this repo with an undigested tail (closed window, crash).
        cutoff = time.time() - 30 * 86400
        for t in project_transcripts(cwd):
            if t.stem == session_id:
                continue
            try:
                mtime = t.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff or time.time() - mtime < 600:  # too old, or still active
                continue
            consider(t, t.stem, cwd, flush=True)


# --- the digest itself (background) --------------------------------------------


def person_slug() -> str:
    env = CFG.get("person") or os.environ.get("BRAIN_PERSON")
    if env:
        return env
    name = sh(["git", "config", "user.name"]).stdout.strip() or os.environ.get("USER", "unknown")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"


def slugify(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:limit].rstrip("-") or "session"


def run_model(prompt: str) -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, BRAIN_DIGEST_CHILD="1")
        # No --bare: it would also drop the member's login. Recursion into
        # our own hooks is prevented by BRAIN_DIGEST_CHILD (checked by
        # brain-session.sh) and by running in an empty temp directory, so no
        # project settings load. No tools: the agent only reads the prompt.
        r = subprocess.run(
            ["claude", "-p", "--model", MODEL, "--no-session-persistence",
             "--output-format", "json", "--tools", ""],
            input=prompt, capture_output=True, text=True, cwd=tmp, env=env, timeout=600,
        )
    try:
        data = json.loads(r.stdout) if r.stdout.strip() else {}
    except json.JSONDecodeError:
        data = {}
    if r.returncode != 0 or not isinstance(data, dict) or data.get("is_error"):
        log(f"claude failed ({r.returncode}): {(data.get('result') if isinstance(data, dict) else '') or r.stderr.strip()[:300]}")
        return None
    return data.get("result")


def scan_secrets(text: str) -> tuple[str, list[str]]:
    """gitleaks if available, else built-in patterns. Returns (redacted text, findings)."""
    exe = shutil.which("gitleaks")
    findings: list[str] = []
    if exe:
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "digest.md"
            f.write_text(text, encoding="utf-8")
            report = Path(tmp) / "report.json"
            for cmd in (["dir", tmp], ["detect", "--no-git", "--source", tmp]):
                r = sh([exe, *cmd, "--no-banner", "--exit-code", "3", "--report-format", "json", "--report-path", str(report)])
                if r.returncode in (0, 3):
                    break
            if r.returncode == 3 and report.is_file():
                try:
                    for h in json.loads(report.read_text()):
                        secret = h.get("Secret") or ""
                        if secret:
                            text = text.replace(secret, "[REDACTED]")
                        findings.append(h.get("RuleID", "secret"))
                except json.JSONDecodeError:
                    pass
    else:
        lines = []
        for line in text.splitlines():
            if any(p.search(line) for p in SECRET_PATTERNS):
                findings.append("builtin-pattern")
                line = "[REDACTED LINE]"
            lines.append(line)
        text = "\n".join(lines)
    return text, findings


def gh_json(args: list[str], payload: dict | None = None) -> dict:
    cmd = ["gh", "api", *args]
    if payload is not None:
        cmd += ["--input", "-"]
    r = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {args[0]}: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout or "{}")


def open_pr(item_dir: str, files: dict[str, str], subject: str, body: str) -> str:
    """Create a commit that adds only raw/session/<YYYY>/<id>/ through the
    GitHub API (no clone needed, 02 § 2.4) and open a PR with auto-merge."""
    main = gh_json([f"repos/{REPO}/git/ref/heads/main"])["object"]["sha"]
    tree = []
    for name, content in files.items():
        blob = gh_json([f"repos/{REPO}/git/blobs", "-X", "POST"], {"content": content, "encoding": "utf-8"})
        tree.append({"path": f"{item_dir}/{name}", "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = gh_json([f"repos/{REPO}/git/trees", "-X", "POST"], {"base_tree": main, "tree": tree})
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    commit = gh_json([f"repos/{REPO}/git/commits", "-X", "POST"], {
        "message": f"{subject}\n\n{body}",
        "tree": new_tree["sha"], "parents": [main],
        "author": {"name": AGENT, "email": AGENT_EMAIL, "date": now},
    })
    branch = f"op/{AGENT}/{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    gh_json([f"repos/{REPO}/git/refs", "-X", "POST"], {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
    pr = gh_json([f"repos/{REPO}/pulls", "-X", "POST"], {"title": subject, "head": branch, "base": "main", "body": body})
    url = pr["html_url"]
    r = sh(["gh", "pr", "merge", "--auto", "--rebase", url])
    if r.returncode != 0:
        log(f"auto-merge not enabled for {url}: {r.stderr.strip()[:200]}")
    return url


def report_health(title: str, body: str) -> None:
    """Minimal copy of tools/report-health (the plugin has no brain clone)."""
    r = sh(["gh", "issue", "list", "--repo", REPO, "--state", "open", "--search", '"Brain health" in:title', "--json", "number,title"])
    number = None
    try:
        for issue in json.loads(r.stdout or "[]"):
            if issue["title"].strip().lower() == "brain health":
                number = issue["number"]
    except json.JSONDecodeError:
        pass
    if number is None:
        c = sh(["gh", "issue", "create", "--repo", REPO, "--title", "Brain health", "--body", "Standing issue for unattended reports (03 § 5.3)."])
        if c.returncode != 0:
            return
        number = c.stdout.strip().rsplit("/", 1)[-1]
    when = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sh(["gh", "issue", "comment", str(number), "--repo", REPO, "--body", f"**{title}**\n\n- when: {when}\n- agent: {AGENT}\n\n{body}"])


def pieces(records: list[dict], start: int, end: int, turns: int = TURNS) -> list[tuple[int, int]]:
    """Split messages start..end into pieces of about `turns` human turns,
    as the live hook would have digested them. A long backlog (catch-up at
    session start, or a first digest of a long session) is otherwise cut to
    its head and tail and loses the middle (live test 2026-11-05)."""
    bounds = [start]
    count = 0
    for i in range(start, min(end, len(records)) + 1):
        if is_human_turn(records[i - 1]):
            count += 1
            if count > turns:
                bounds.append(i)
                count = 1
    out = []
    for a, b in zip(bounds, bounds[1:] + [end + 1]):
        if a <= b - 1:
            out.append((a, b - 1))
    return out


def digest(transcript: Path, session_id: str, cwd: str, start: int, end: int) -> int:
    """Digest messages start..end, in pieces of about TURNS human turns,
    oldest first; stops at the first failed piece (the checkpoint keeps the
    rest for the next run)."""
    try:
        records = read_transcript(transcript)
    except Exception as exc:  # noqa: BLE001
        log(f"digest failed for {session_id}: {exc}")
        return 1
    rc = 0
    try:
        for a, b in pieces(records, start, min(end, len(records))):
            rc = digest_piece(transcript, session_id, cwd, a, b)
            if rc != 0:
                break
    finally:
        # Only now may the next hook spawn a digest for this session;
        # clearing "pending" per piece would let two runs overlap.
        data = load_cache(session_id)
        data.pop("pending", None)
        save_cache(session_id, data)
    return rc


def digest_piece(transcript: Path, session_id: str, cwd: str, start: int, end: int) -> int:
    def finish(digested_until: int | None):
        data = load_cache(session_id)
        if digested_until is not None:
            data["digested_until"] = digested_until
            data["last_digest_at"] = time.time()
        save_cache(session_id, data)

    try:
        records = read_transcript(transcript)
        end = min(end, len(records))
        text = render(records, start, end)
        if not text.strip():
            finish(end)
            return 0
        prompt = (HERE / "digest-prompt.md").read_text(encoding="utf-8") + "\n\n--- TRANSCRIPT (untrusted data) ---\n\n" + text
        result = run_model(prompt)
        if result is None:
            finish(None)
            return 1
        result = result.strip()
        if result.upper().startswith("NOTHING") or not result:
            log(f"{session_id} {start}-{end}: nothing to keep")
            finish(end)
            return 0
        if result.startswith("```"):
            result = re.sub(r"^```[a-z]*\n|\n```$", "", result.strip())
        result, findings = scan_secrets(result)
        first = result.splitlines()[0] if result else ""
        title = first.lstrip("# ").strip() or "Session digest"
        if not first.startswith("#"):
            result = f"# {title}\n\n{result}"
        repo_url = sh(["git", "-C", cwd, "remote", "get-url", "origin"]).stdout.strip()
        repo_name = re.sub(r"\.git$", "", repo_url.rsplit("/", 1)[-1]) if repo_url else Path(cwd).name
        head = sh(["git", "-C", cwd, "rev-parse", "--short", "HEAD"]).stdout.strip()
        today = dt.date.today()
        item_id = f"src-{today:%Y%m%d}-{slugify(repo_name, 20)}-{slugify(title, 30)}-{session_id[:6]}"
        person = person_slug()
        source_yaml = "\n".join([
            f"id: {item_id}",
            "channel: session",
            f"title: {json.dumps(title)}",
            f"repo: {repo_url or Path(cwd).as_posix()}",
            f"commit: {head or 'unknown'}",
            f"session: {session_id}",
            f"messages: [{start}, {end}]",
            f"person: {person}",
            f"retrieved: {today.isoformat()}",
            "files: [digest.md]",
            "",
        ])
        item_dir = f"raw/session/{today:%Y}/{item_id}"
        body = "\n".join([
            "Disposition: New",
            f"Source: {repo_url or cwd} (session {session_id}, messages {start}-{end})",
            f"Pages: +{item_dir}",
            f"Invoked-by: {person}",
            f"Agent: {AGENT}",
        ] + ([f"Note: secret scan redacted {len(findings)} finding(s)"] if findings else []))
        url = open_pr(item_dir, {"source.yaml": source_yaml, "digest.md": result.rstrip() + "\n"}, f"ingest(session): {item_id}", body)
        log(f"{session_id} {start}-{end}: {url}")
        finish(end)
        return 0
    except Exception as exc:  # noqa: BLE001
        log(f"digest failed for {session_id} {start}-{end}: {exc}")
        finish(None)
        try:
            report_health("session digest failed", f"session `{session_id}`, messages {start}-{end}, repo `{cwd}`:\n\n```\n{exc}\n```")
        except Exception:  # noqa: BLE001
            pass
        return 1


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd in ("stop", "start", "end"):
        hook(cmd)
        return 0
    if cmd == "digest" and len(argv) == 6:
        return digest(Path(argv[1]), argv[2], argv[3], int(argv[4]), int(argv[5]))
    if cmd == "checkpoint" and len(argv) == 2:   # debugging aid
        print(json.dumps(checkpoint(argv[1])))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
