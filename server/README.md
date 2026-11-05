# Server setup (06-ops.md)

What runs on the group GPU server: the compile worker, the central qmd
with its auth proxy, and (later) PDF conversion and the Mattermost bot.

## 1. Clone and tools

```bash
sudo useradd -m brain
sudo -iu brain
git clone git@github.com:slds-lmu/brain-group.git ~/brain-group   # full clone incl. LFS
sudo apt install python3-yaml gitleaks                                # or pip install pyyaml + gitleaks release
npm install -g @anthropic-ai/claude-code                              # the agent CLI
# qmd: pin a version (01 § 7); it needs ~2 GB of local models for hybrid mode
```

## 2. GitHub App (06 § 4)

Create a GitHub App in `slds-lmu` with permissions *Contents: read &
write*, *Pull requests: read & write*, *Issues: read & write*, *Metadata:
read*. Install it on the brain repo only. Note the App id and the
installation id, download the private key. Allow the App to bypass the
PR requirement for the index Action if you use the App's token there
(workflow `index.yml`), or let the `brain-agent-index` commits in via a
branch-protection bypass.

Git pushes use the token too: the worker's clone should use HTTPS with a
credential helper that reads `GH_TOKEN`, e.g.

```bash
git config --global credential.helper '!f() { echo "username=x-access-token"; echo "password=$GH_TOKEN"; }; f'
```

## 3. Configuration

`/etc/brain/worker.env` (readable by the `brain` user only):

```
BRAIN_DIR=/home/brain/brain-group
BRAIN_REPO=slds-lmu/brain-group
BRAIN_MODEL=sonnet
BRAIN_POLL=300
BRAIN_QMD=qmd update
ANTHROPIC_API_KEY=…                       # group key with a monthly limit (06 § 5)
BRAIN_APP_ID=…
BRAIN_APP_INSTALLATION_ID=…
BRAIN_APP_KEY=/etc/brain/app-key.pem
QMD_UPSTREAM=http://127.0.0.1:8182/mcp
PROXY_PORT=8181
```

## 4. Services

```bash
sudo cp server/brain-worker.service server/brain-qmd-proxy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now brain-worker brain-qmd-proxy
journalctl -u brain-worker -f
```

Try one cycle by hand first: `BRAIN_DIR=~/brain-group python3 server/worker.py --once --dry-run`.

## 5. What the worker does every cycle

1. `git pull --ff-only origin main`.
2. Queue = `tools/check_evidence --queue` (raw items without a summary page).
3. For each item: `tools/start-op --agent brain-agent-compile`, then a
   `claude -p` run with the brain plugin and `server/compile-prompt.md`
   that compiles the item and commits via `tools/commit-op` (PR with
   auto-merge). Success is verified by the item leaving the queue after
   the next pull. Three failures → a comment on the "Brain health" issue
   and a 24-hour backoff for that item.
4. `qmd update` to re-index.

The worker keeps no state besides the backoff file in
`~/.cache/brain-worker/`, which may be deleted at any time.

## 6. Search access (06 § 3, Q9)

`qmd-mcp-proxy.py` sits in front of qmd's MCP endpoint and admits a request
only if the `Authorization: Bearer <GitHub token>` belongs to someone with
read access to the brain repo. Members set `BRAIN_QMD_URL=https://<server>/mcp`
and `BRAIN_GITHUB_TOKEN=$(gh auth token)` in their shell; the plugin's
`.mcp.json` picks both up. Put TLS in front of the proxy.

## Still open (06 § 8)

- LFS limits and cost of the `slds-lmu` plan.
- GitHub Actions minutes for the private repo.
- Who administers the worker and the API key.
- The qmd version to pin, and the `qmd mcp` HTTP flags of that version.
- PDF converter (MinerU vs Marker): decided by the 10-paper benchmark.
