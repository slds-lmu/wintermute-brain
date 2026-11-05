#!/usr/bin/env python3
"""Shared helpers for the brain's tools (index, lint, check_evidence, commit-op).

Context: imported by the scripts in tools/. Pure stdlib plus PyYAML
(python3-yaml). Everything here is derived from the repo: no state of
its own (CLAUDE.md, "the repo is complete").

Specs: 01-data-model.md (layout, frontmatter, links), 03-agent-ops.md
(write path, lint), v0-foundation.md.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - environment problem, not a code path
    sys.exit("brain tools need PyYAML: apt install python3-yaml  (or pip install pyyaml)")

# --- Constants from 01-data-model.md -----------------------------------------

# 01 § 5.2: the six page types. A type exists only if membership is indisputable.
TYPES = ("person", "meeting", "paper", "grant", "source", "page")

# 01 § 2: raw channels.
CHANNELS = ("web", "paper", "mattermost", "session", "mail", "doc", "meeting")

# 01 § 5.1: OKF status values; absent means stable.
STATUSES = ("draft", "stable", "deprecated")

# 01 § 5.1: description is the page's index line, so it must stay short.
DESCRIPTION_MAX = 140

# 01 § 5.2: type-specific frontmatter that must be present.
REQUIRED_EXTRA = {
    "meeting": ("date",),
    "paper": ("authors", "year"),
}

# 01 § 3: slugs are lowercase kebab-case ASCII.
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Index files are generated (01 § 7) and never count as pages.
INDEX_RE = re.compile(r"^index(?:-[a-z0-9]+-[a-z0-9]+)?\.md$")

# Text files inside raw items that count as evidence; source.yaml is bookkeeping.
RAW_TEXT_SUFFIXES = (".md", ".txt", ".tex", ".html", ".json", ".csv")

# --- Repo root ---------------------------------------------------------------


def repo_root(start: Path | None = None) -> Path:
    """The brain repo root: the git toplevel if inside git, else the first
    ancestor that has a wiki/ folder. Works inside worktrees too."""
    start = (start or Path.cwd()).resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start, capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out:
            return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    for candidate in (start, *start.parents):
        if (candidate / "wiki").is_dir():
            return candidate
    return start


# --- Frontmatter -------------------------------------------------------------

FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)


@dataclass
class Page:
    path: Path                 # absolute
    rel: str                   # repo-relative posix path, e.g. wiki/page/mlr3.md
    type_dir: str              # folder name under wiki/
    slug: str                  # file stem
    frontmatter: dict | None   # None if missing or unparsable
    body: str                  # text after the frontmatter
    error: str | None = None   # frontmatter parse error, if any
    text: str = field(default="", repr=False)


def split_frontmatter(text: str) -> tuple[dict | None, str, str | None]:
    """Return (frontmatter dict, body, error). A page without a leading
    `---` block has no frontmatter (error set)."""
    m = FM_RE.match(text)
    if not m:
        return None, text, "no YAML frontmatter block at the top of the file"
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:  # keep the first line of the YAML error only
        return None, text[m.end():], f"invalid YAML frontmatter: {str(exc).splitlines()[0]}"
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return None, text[m.end():], "frontmatter is not a mapping"
    return data, text[m.end():], None


def load_page(root: Path, path: Path) -> Page:
    text = path.read_text(encoding="utf-8")
    fm, body, err = split_frontmatter(text)
    rel = path.resolve().relative_to(root.resolve()).as_posix()
    parts = rel.split("/")
    type_dir = parts[1] if len(parts) >= 3 and parts[0] == "wiki" else ""
    return Page(path=path, rel=rel, type_dir=type_dir, slug=path.stem,
                frontmatter=fm, body=body, error=err, text=text)


def is_index_file(path: Path) -> bool:
    return bool(INDEX_RE.match(path.name))


def iter_page_paths(root: Path) -> list[Path]:
    """All wiki pages: wiki/<type>/<slug>.md, index files excluded."""
    wiki = root / "wiki"
    if not wiki.is_dir():
        return []
    out = []
    for type_dir in sorted(wiki.iterdir()):
        if not type_dir.is_dir():
            continue
        for p in sorted(type_dir.glob("*.md")):
            if not is_index_file(p):
                out.append(p)
    return out


def iter_pages(root: Path) -> list[Page]:
    return [load_page(root, p) for p in iter_page_paths(root)]


# --- Links -------------------------------------------------------------------

LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


@dataclass(frozen=True)
class Link:
    line_no: int       # 1-based line in the file
    text: str
    target: str        # as written
    kind: str          # internal | fixable | relative | external | anchor
    path: str | None   # repo-relative path without leading slash and fragment


def classify_target(target: str) -> tuple[str, str | None]:
    """01 § 6: internal links are root-absolute (/wiki/…, /raw/…).
    Slash-less wiki/… or raw/… is Obsidian's form and gets rewritten."""
    if target.startswith("#"):
        return "anchor", None
    if SCHEME_RE.match(target) or target.startswith("//"):
        return "external", None
    bare = target.split("#", 1)[0].split("?", 1)[0]
    if target.startswith("/"):
        return "internal", bare.lstrip("/")
    if bare.startswith(("wiki/", "raw/")):
        return "fixable", bare
    return "relative", bare


def iter_lines_outside_fences(text: str):
    """Yield (line_no, line) for lines outside fenced code blocks, with
    inline code blanked out so `[x](y)` inside backticks is not a link."""
    fence = None
    for i, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        yield i, INLINE_CODE_RE.sub(lambda mm: " " * len(mm.group(0)), line)


def extract_links(text: str) -> list[Link]:
    links = []
    for line_no, line in iter_lines_outside_fences(text):
        for m in LINK_RE.finditer(line):
            kind, path = classify_target(m.group(2))
            links.append(Link(line_no, m.group(1), m.group(2), kind, path))
    return links


def normalise_links(text: str) -> tuple[str, int]:
    """Safe fix (03 § 5.1): rewrite `](wiki/…)` and `](raw/…)` to the
    root-absolute form. Returns (new text, number of rewrites)."""
    count = 0
    out = []
    fence = None
    for line in text.splitlines(keepends=True):
        m = FENCE_RE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            out.append(line)
            continue
        if m:
            fence = m.group(1)
            out.append(line)
            continue

        def repl(mm: re.Match) -> str:
            nonlocal count
            target = mm.group(2)
            if classify_target(target)[0] == "fixable":
                count += 1
                return f"[{mm.group(1)}](/{target})"
            return mm.group(0)

        # Protect inline code spans from rewriting.
        pieces = []
        last = 0
        for code in INLINE_CODE_RE.finditer(line):
            pieces.append(LINK_RE.sub(repl, line[last:code.start()]))
            pieces.append(code.group(0))
            last = code.end()
        pieces.append(LINK_RE.sub(repl, line[last:]))
        out.append("".join(pieces))
    return "".join(out), count


# --- Raw items ---------------------------------------------------------------


def raw_item_dirs(root: Path) -> list[Path]:
    """Every raw/<channel>/<YYYY>/<id>/ folder (01 § 4)."""
    raw = root / "raw"
    if not raw.is_dir():
        return []
    out = []
    for channel in sorted(raw.iterdir()):
        if not channel.is_dir():
            continue
        for year in sorted(channel.iterdir()):
            if not year.is_dir():
                continue
            out.extend(sorted(d for d in year.iterdir() if d.is_dir()))
    return out


def raw_dir_for_id(root: Path, source_id: str) -> Path | None:
    """Resolve a summary page's slug to its raw folder (01 § 3: shared id)."""
    for d in raw_item_dirs(root):
        if d.name == source_id:
            return d
    return None


def summary_page_for_raw(root: Path, raw_dir: Path) -> Path | None:
    """A raw item has exactly one summary page: paper → wiki/paper, else wiki/source."""
    channel = raw_dir.parent.parent.name
    type_dir = "paper" if channel == "paper" else "source"
    page = root / "wiki" / type_dir / f"{raw_dir.name}.md"
    return page if page.is_file() else None


def load_source_yaml(raw_dir: Path) -> dict | None:
    p = raw_dir / "source.yaml"
    if not p.is_file():
        return None
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


# --- Agents ------------------------------------------------------------------

AGENT_LINE_RE = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*<([^>]+)>\s*$")


def load_agents(root: Path) -> dict[str, str]:
    """agents.txt (03 § 6.1): `name <email>` per line. Returns name → email."""
    p = root / "agents.txt"
    agents: dict[str, str] = {}
    if not p.is_file():
        return agents
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = AGENT_LINE_RE.match(line)
        if m:
            agents[m.group(1)] = m.group(2).strip().lower()
    return agents


def agent_emails(root: Path) -> set[str]:
    return set(load_agents(root).values())


# --- Git ---------------------------------------------------------------------


class GitError(RuntimeError):
    pass


def git(args: list[str], cwd: Path, check: bool = True, env: dict | None = None) -> str:
    """Run git and return stdout. Raises GitError with stderr on failure."""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=full_env)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def git_ok(args: list[str], cwd: Path) -> bool:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True).returncode == 0


def ref_exists(ref: str, cwd: Path) -> bool:
    return git_ok(["rev-parse", "--verify", "--quiet", ref], cwd)


def show_file(rev: str, rel: str, cwd: Path) -> str | None:
    """Contents of rel at rev, or None if it does not exist there."""
    proc = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=cwd, capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def changed_files(base: str, head: str, cwd: Path, paths: list[str] | None = None) -> list[tuple[str, str]]:
    """[(status, path)] between base and head. Status is A, M, D (renames
    are reported as D + A so raw-immutability catches them)."""
    args = ["diff", "--name-status", "--no-renames", base, head]
    if paths:
        args += ["--", *paths]
    out = []
    for line in git(args, cwd).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out.append((parts[0][0], parts[-1]))
    return out


def worktree_changes(base: str, cwd: Path) -> list[tuple[str, str]]:
    """Changes between base and the working tree, including untracked files."""
    out = []
    for line in git(["diff", "--name-status", "--no-renames", base], cwd).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            out.append((parts[0][0], parts[-1]))
    for rel in git(["ls-files", "--others", "--exclude-standard"], cwd).splitlines():
        if rel:
            out.append(("A", rel))
    return out


def blame_authors(rev: str, rel: str, cwd: Path) -> list[tuple[str, int]]:
    """Per line of rel at rev: (author email lowercased, author epoch time)."""
    proc = subprocess.run(
        ["git", "blame", "--line-porcelain", rev, "--", rel],
        cwd=cwd, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise GitError(f"git blame failed for {rel}@{rev}: {proc.stderr.strip()}")
    out = []
    mail = ""
    when = 0
    for line in proc.stdout.splitlines():
        if line.startswith("author-mail "):
            mail = line[len("author-mail "):].strip().strip("<>").lower()
        elif line.startswith("author-time "):
            when = int(line[len("author-time "):].strip())
        elif line.startswith("\t"):
            out.append((mail, when))
    return out


def last_commit_time(rel: str, cwd: Path, rev: str = "HEAD") -> int | None:
    out = git(["log", "-1", "--format=%ct", rev, "--", rel], cwd, check=False).strip()
    return int(out) if out else None


def first_commit_time(rel: str, cwd: Path, rev: str = "HEAD") -> int | None:
    out = git(["log", "--diff-filter=A", "--format=%ct", rev, "--", rel], cwd, check=False).split()
    return int(out[-1]) if out else None


# --- Findings ----------------------------------------------------------------


@dataclass
class Finding:
    level: str      # error (blocks) | warn (report) | info | fixed
    rule: str
    path: str
    message: str
    line: int | None = None

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"{self.level:<5} {self.rule:<16} {where}: {self.message}"
