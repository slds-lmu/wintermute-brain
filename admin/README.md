# Admin tools

Tools that only repository admins run. They are **not** part of the
plugin, so members and agents never have them.

## Erasure runbook (06 § 7a, PD2)

When a person asks for their data to be **erased** (not just removed
from the current pages):

1. **Remove it from the current pages first**, with a normal edit PR, so
   it disappears from the wiki right away.
2. **Find what to erase:** the raw item folders and summary pages
   (`--path`), and/or names or sentences elsewhere (`--replace-text`, one
   `literal==>***REMOVED***` per line).
3. **Dry run** (default) and check the report:
   `admin/erase --repo slds-lmu/wintermute-brain-content-slds --path … --replace-text names.txt`
4. **Announce a short freeze** (no ingests, no open PRs), then run with
   `--execute`. The script checks that you are an admin, writes a backup
   bundle, rewrites the history with git-filter-repo, verifies, and
   force-pushes. The force-push only works for admins (ruleset).
5. **Afterwards:**
   - close all open PRs of the content repo (they point at old commits);
   - ask **GitHub Support** to purge cached views, PR refs and LFS
     objects of the old commits ("remove sensitive data" process);
   - tell members to delete and re-clone their content clone;
   - re-clone the content repo on the server (worker and qmd index);
   - check backups outside GitHub, if any (`parked.md` K30);
   - verify, then **delete the backup bundle** (it still holds the data).

Requirements on the admin's machine: `git`, `gh` (logged in as an
admin of the content repo), `git-filter-repo`.
