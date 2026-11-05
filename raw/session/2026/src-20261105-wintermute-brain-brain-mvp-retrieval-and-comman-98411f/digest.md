# Brain MVP: retrieval and command decisions, no direct pushes to main, token setup

- **R1 (user):** Hybrid search from the MVP, not keyword-only first. It runs on the GPU server anyway, and session digests are worded differently from later questions.
- **R2 (user):** The agent uses both wiki pages and raw sources, and tells the user which parts of an answer come from which. The earlier recommendation was wiki-first.
- **R3 (user):** The `wiki/page/` index is generated and split by first letter (`index-a-f.md`, …). The assistant's revised suggestion to skip splitting was not taken.
- **U1 (user):** Commands are `/brain-ingest`, `/brain-ask`, `/brain-edit`, `/brain-lint`.
- **U2 (user):** Querying works from any repo with the plugin, through the server's qmd. A local brain clone is optional: it is needed for the offline fallback and for editing. Ingest and edit still use a local working copy.
- **Spec 03 §2.1 changed (user):** Nobody pushes directly to `main`, humans included; they use PRs. The user saw no need for direct pushes. The only exception is the index Action, which needs the brain GitHub App (not created yet).

**Implementation status:**
- Marc's PR #1 (`d0cd9e1`) implemented the MVP from specs 00–06, which are now marked accepted.
- Local results: 38 tests pass; lint reports 0 errors and 0 warnings.
- The `check` and `index` workflows have run green on GitHub.
- Not done: branch protection or ruleset, the GitHub App, qmd pinning, and a real-transcript test of the session hook (so far only a fake transcript).
- Auto-merge, rebase and squash merge are enabled on the repo.
- The ruleset is deferred. It is not blocking for a first test, but it becomes necessary before unattended agents or other members join. It has to come together with the GitHub App, because otherwise the index Action cannot push.

**Token setup for slds-lmu (convention):**
- A fine-grained PAT has one resource owner, fixed at creation. An org admin role does not extend a personal token to another org's repos, so each owner needs its own token.
- Tokens live in `~/.gh-tokens/<name>` on the host and are mounted read-only into yolobox. `ghr <name> …` and `gitr <name> …` run `gh` or `git` with that token; plain `gh` uses the default token.
- For `wintermute-brain`, a token needs Actions read, otherwise check status cannot be read. The user created `slds-write`, scoped to this one repo, and added Actions read/write. It works.
- The assistant recommended `gh auth login` for general work. The user chose per-project tokens instead.

**Open:**
- Whether to install `defuddle` and `gitleaks` in the sandbox for a first real `/brain-ingest` test. The assistant asked; no answer yet.
- Remaining checks: LFS limits, Actions minutes, and who administers the server worker and API key (`06-ops.md` §8); the PDF converter benchmark, qmd at scale, and the Obsidian link check (`today.md` §4).
