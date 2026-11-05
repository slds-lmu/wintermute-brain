# Brain design: lint reporting, agent commit identity, ops decisions Q1–Q9

- **Lint reports (O3), decided by the owner:** no report files in the repo. Failures of unattended operations and scheduled lint runs go to one standing GitHub issue, "Brain health", with one comment per event so subscribers are notified. A repo file would just go stale. A Mattermost ping mirror is parked as K29.
- **Agent commit identity (O4):** agent commits use a dedicated author per agent kind (e.g. `brain-agent-compile`), listed in `agents.txt`. Every other author counts as human. The triggering human goes into an `Invoked-by:` trailer. The author survives merges, while GitHub overwrites the committer on rebase merges.
- **Merge method:** the owner chose rebase-and-merge as a trial, to keep one commit per operation in a linear history. Merge commits are the fallback if it causes problems.
- **Q1, what runs where (accepted):** members' machines run Claude Code with the brain plugin (commands, session hooks, digest agent). The GPU server runs the compile worker, qmd, PDF conversion, and later the Mattermost bot. GitHub is the gate and the record.
- **Q2, search:** qmd runs centrally on the server, not on each member's machine. If it is unreachable, agents fall back to the indexes plus grep on the local clone.
- **Q3, distribution:** the brain ships as a Claude Code plugin from the wintermute marketplace, declared in each project repo's committed `.claude/settings.json`. Members install git, `gh` and gitleaks once. `defuddle` and `slds-paper-litdownload` are needed only by people who ingest web pages or papers by hand. gitleaks must scan before anything leaves the machine.
- **Q4 and Q5, server:** the worker polls every 5 minutes (pull, compile new raw items, re-index qmd), so no inbound access is needed. It authenticates as a GitHub App installed on the brain repo only, with short-lived tokens and no paid seat.
- **Q6, cost:** members use their own Claude accounts. The server uses a group Anthropic API key with a monthly spending limit, to be set after measuring the first weeks.
- **Q7, large files:** PDFs stay in git LFS (D2). Member clones skip LFS downloads by default, and only the server fetches PDFs. The original PDF lets extraction be redone with a better converter.
- **Q8, backups:** GitHub only, plus branch protection on `main` (no force-push, no deletion). An off-GitHub backup is parked as priority K30.
- **Q9, search access:** per person. Only people with read access to the brain repo may query the server's qmd, checked against their GitHub token through an auth proxy. The owner rejected a shared token.
- **Open checks:** LFS limits of the `slds-lmu` plan, GitHub Actions minutes for a private repo, and who administers the server worker and the API key.
- **Status:** `specs/06-ops.md` is written as a draft. `04-retrieval.md` and `05-interfaces.md` are still to write.
