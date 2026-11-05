# wintermute-brain - code of the SLDS brain

The SLDS brain is an LLM-maintained group wiki: immutable raw sources,
agent-written Markdown pages, git as the log and the provenance. **This
repo is the code and the design.** The content lives in separate repos,
one per confidentiality tier (01 § 1):

| Repo | Holds |
|---|---|
| `slds-lmu/wintermute-brain` (this) | tools, Claude Code plugin, server, reusable workflows, specs, tests |
| `slds-lmu/wintermute-brain-content-slds` | `raw/`, `wiki/`, indexes, templates, `agents.txt`, the agents' `CLAUDE.md`, `.brain-version` |

A content repo pins the code it uses in `.brain-version` (a release tag
of this repo). Its CI calls this repo's reusable workflows at that tag;
the server worker checks out the same tag. Upgrading = a PR in the
content repo that changes `.brain-version` and the workflow refs.

```
plugin/            Claude Code plugin: /brain-ingest, /brain-ask, /brain-edit, /brain-lint,
                   brain skill, session-digest hooks, qmd MCP config
plugin/tools/      index, lint, check_evidence, start-op, commit-op, log, report-health
server/            container runtime, qmd gateway and GPU coordinator, compile worker, credential helpers
.github/workflows/ check.yml (tests of this repo); brain-check.yml and brain-index.yml
                   (reusable, called by content repos)
                   server-image.yml (immutable GHCR builds for server deployment)
tests/             fixture wiki, one broken copy per lint rule, git-flow tests
specs/             the design (00-06), prior art, parked ideas, implementation status
```

## Tools

Stdlib Python 3.10+ plus PyYAML. Run them from inside a content clone (or
one of its operation worktrees); they work on the repo they are run in.

```bash
T=plugin/tools                 # or the installed plugin's tools/ folder
$T/index                       # regenerate all index files (--check to verify)
$T/lint [--fix] [--base REV] [--agent NAME]   # mechanical lint (03 § 5.1)
$T/check_evidence [pages]      # grounding (--queue: compile backlog, oldest first)
$T/start-op --agent NAME       # fresh worktree for one operation
$T/commit-op ...                 # the agents' only write path: lint, preconditions, PR with auto-merge
$T/log [--op ingest]           # readable digest of the git log
python3 -m unittest discover -s tests   # in this repo
```

## Releases

Tag `vX.Y.Z` on `main` after the tests pass; content repos move to it by
PR. This repo never collects session digests (01 § 1).

## Status

See `specs/implementation-status.md`.
