# brain — Claude Code plugin

The member-side half of the SLDS brain (05-interfaces.md, 06 § 2): the
commands, the `brain` skill, the automatic session-digest hooks and the
MCP connection to the server's search.

## Commands (05 § 2)

| Command | Does | writes |
|---|---|---|
| `/brain-ingest <url \| doi \| arXiv id \| file>` | ingest one source | raw/ + wiki/ |
| `/brain-ask <question>` (or just ask) | answer from the wiki with citations | nothing |
| `/brain-edit <request>` | change pages on request | wiki/ |
| `/brain-lint` | mechanical lint + grounding check + LLM judgment report | safe fixes |

## Install

The plugin is published through the wintermute marketplace. In the
marketplace's `.claude-plugin/marketplace.json`, add:

```json
{
  "name": "brain",
  "description": "SLDS brain: LLM-maintained group wiki",
  "source": { "source": "github", "repo": "slds-lmu/wintermute-brain", "path": "plugin" }
}
```

The plugin includes the brain tools (`tools/`), so members need no clone
of the code repo. Each project repo that wants session digests (02 § 2.1)
commits this `.claude/settings.json` (the content repo does the same; the
code repo `wintermute-brain` never does, 01 § 1):

```json
{
  "extraKnownMarketplaces": {
    "wintermute": { "source": { "source": "git", "url": "git@github.com:slds-lmu/wintermute.git" } }
  },
  "enabledPlugins": { "brain@wintermute": true }
}
```

Per member, once:

```bash
# tools (06 § 2)
sudo apt install gitleaks            # or a pinned release; secret scan before a digest leaves the machine
npm install -g defuddle              # web ingest only
# a clone for ingest/edit/lint (not needed for /brain-ask or digests).
# Clone over HTTPS, not SSH: git then uses the same token as `gh` (which
# opens the PRs), and it works in containers and on the server without SSH
# keys (live test 2026-11-05).
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/slds-lmu/wintermute-brain-content-slds.git ~/wintermute-brain-content-slds
# environment (shell profile)
export BRAIN_DIR=~/wintermute-brain-content-slds
export BRAIN_REPO=slds-lmu/wintermute-brain-content-slds
export BRAIN_PERSON=first-last
export BRAIN_QMD_URL=https://<server>/mcp
export BRAIN_GITHUB_TOKEN=$(gh auth token)
```

## Session digests (02 § 2)

`hooks/hooks.json` runs `scripts/brain-session.sh` on Stop, SessionStart
and SessionEnd. The script forks `scripts/brain_session.py digest …` into
the background when there are 20+ new human turns or 30+ minutes since
the last digest (tunable: `BRAIN_DIGEST_TURNS`, `BRAIN_DIGEST_MINUTES`).
The digest agent (`claude -p --model haiku`, no tools, your own account)
reads only the new part of the transcript with `scripts/digest-prompt.md`
and answers `NOTHING` or a short digest. gitleaks redacts secrets, then a
PR adding only `raw/session/<YYYY>/<id>/` is opened through the GitHub
API with auto-merge. The server compiles it into pages.

- Disable for a session: `BRAIN_SESSION_DIGEST=off`.
- Logs: `~/.cache/brain/digest.log`, `~/.cache/brain/hook.log`.
- Checkpoints are derived from the brain repo (`source.yaml` has
  `session` and `messages`); `~/.cache/brain/sessions/` is only a cache.
