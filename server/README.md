# Brain server

## DESCRIPTION

The server provides authenticated qmd search and a compile worker for
slds-lmu/wintermute-brain-content-slds. The application, Dockerfile, and
image workflow live in slds-lmu/wintermute-brain. The GPU infrastructure repository owns Compose,
Ansible, Caddy, host paths, secrets, monitoring, and the deployed image pin.

The search endpoint is:

    https://api.wintermute-gpu.stat.uni-muenchen.de/brain/mcp

Clients send a personal GitHub token in the Authorization bearer header.
The gateway verifies the user and repository read permission. Access
decisions are cached using token hashes, for five minutes when allowed and
30 seconds when denied; plaintext tokens are forwarded only to GitHub. The
qmd HTTP listener is container-local.

A failed check answers 401 only when GitHub denied the token. When GitHub
is unreachable, rate-limited, or answers with a server error, a token allowed
within the last hour keeps working and any other token receives 503 with
Retry-After. Such failures are not cached. Tokens that cannot be valid never
reach GitHub. Each client address may check 30 tokens per minute that are not
in the cache, and further ones receive 429. At most eight checks run at a
time and 64 may be pending; concurrent requests for one token share a check.

The compile worker uses /internal/mcp with a shared service token. Caddy
exposes only /mcp and /healthz; the internal route is confined to the Compose
network. Set BRAIN_QMD_URL to http://brain-search:8181/internal/mcp and
BRAIN_GITHUB_TOKEN to the service token in the worker environment.

## CONTAINERS AND STORAGE

The search and worker containers use the same image with different commands.
Only search receives GPU devices. The image contains application code,
Node, qmd, Claude Code, git, Git LFS, gh, and gitleaks. Model files and wiki
content are persistent mounts outside the image.

The worker command is python3 /opt/brain/server/worker.py. It creates the
content clone if missing, polls main every five minutes, updates BRAIN_CODE_DIR
to the latest main of the code repository, like CI and members, and compiles
the derived backlog using its plugin/tools. Set BRAIN_AUTO_COMPILE=false to
retain synchronization without running the agent. BRAIN_QMD is empty: indexing belongs to search.
Search waits for the worker's initial checkout marker before opening the
repository. Text indexing runs when main changes; pending embeddings are
resumed independently without clearing query caches on every poll.

Keep the clone, qmd SQLite database, and model cache on a local filesystem
with working POSIX locks. The database and models are derived state.
Monitor their space use together with Docker storage. The server clone
fetches LFS files; GitHub remains the authoritative content store.

## GPU

One qmd process runs on the GPU next to Whisper and MinerU and serves every MCP
call. It does not yield the GPU and takes no GPU lock. Measured on the V100 with
16 GB, on real documents of 25 to 280 pages, including scans at 300 dpi and 24
tables:

| Load beside OCR | OCR time | Search, median and maximum | GPU memory |
| --- | --- | --- | --- |
| One search at a time | +3-4% | 2.2 s, 7 s | 10.5 GB |
| Also continuous transcription | +6-8% | 2.2 s, 10 s | 10.5 GB |
| Four parallel searches and transcription | +15-16% | 3.5 s, 16 s | 11.7 GB |

OCR output stayed byte-identical. Whisper holds about 2.6 GB, MinerU about 3.4 GB at
its allowance of 8 GB, and qmd 3.4 GB plus about 0.5 GB per further running search.
An earlier design unloaded qmd for OCR and answered from a CPU qmd, in 30 to 70
seconds with one search at a time.

Transcription was measured beside OCR at allowance 8 and two continuous searches,
on 60 seconds of speech. Text stayed byte-identical and memory peaked at 10.5 GB.

| Load | Quiet GPU | Beside OCR and search |
| --- | --- | --- |
| Realtime session, partial results | 101 | 63 |
| Realtime session, commit to final text | 0.24 s | 0.23 s |
| Three realtime sessions, partial results in total | 185 | 102 |
| Three realtime sessions, commit to final text | 0.4-0.7 s | 1.1-2.3 s |
| Eight parallel transcriptions, wall time | 8.7 s | 14.8 s |

Partial results stayed current in all of these, at 0.15 s for the 95th percentile.
The 280-page OCR under this load took 333 s, against 282 s alone. Searches took 2.6 s
at the median and 12 s at most.

qmd loads its models for the first search, in about ten seconds, and unloads them
after five idle minutes, by a fixed setting in its createStore. It then holds about
350 MB. The coordinator warms them once when qmd starts.

The gateway starts qmd's server directly: qmd's launcher is a separate parent
process that exits before the server does, so killing and waiting would otherwise
act on the wrong process. Without GPU access qmd fails to load, as the image holds
no CPU backend, and /healthz answers 503.

Index updates and embeddings run every BRAIN_INDEX_POLL seconds beside the running
qmd, which qmd supports through WAL and a 120-second busy timeout. If one fails,
qmd keeps serving the current index and /healthz answers 503. This also holds when
qmd starts. On a new database it then answers without results until a refresh works.

## GPU MEMORY SHORTAGE

Without enough GPU memory for its models, qmd answers HTTP 200 with no results and
no error, even for words in the wiki, and the next query after that crashes it
(SIGILL). It reports the failure only in its log. The gateway therefore reads that log:
a search during which it reports the failure receives 503, and qmd restarts. Until
its models fit, /healthz answers 503 and new calls receive 503 at once, so that clients
use their local fallback. When only the query expansion lacks memory, qmd searches
without it and the gateway logs a warning. The rerank fallback score that qmd writes
to its persistent cache can outlive such a shortage for the affected query.

A model loaded with too little GPU memory can also land partly on the CPU, without any
message, and stays there after memory returns: searches then take 10-12 s at 500-700%
CPU, and qmd holds 2.4 GB instead of 3.4 GB. qmd therefore starts only with
BRAIN_QMD_GPU_MIB free. A first search after idling during a shortage can still cause
this state, which ends when qmd unloads its models after five idle minutes, or restarts.

The gateway drops qmd's per-request log entries, which contain the query text and can
span lines. qmd has no setting for this.

## ROUTING

| Call | Handling |
| --- | --- |
| tools/call query | Two run at a time; BRAIN_SEARCH_LIMIT run or wait in total |
| subscriptions/listen | qmd, with an empty notification filter |
| server/discover, initialize | qmd, with listChanged removed from the answer |
| Everything else | qmd, with no limit; these calls load no model |

Each running search allocates GPU memory, hence the limit. Beyond BRAIN_SEARCH_LIMIT
a search receives 503 at once. Claude Code abandons a request after 60 seconds
without response headers, and qmd sends none before its answer is complete, so a
search without an answer after BRAIN_SEARCH_WAIT seconds receives 503. qmd cannot
cancel a search, so the gateway restarts qmd if that search spent over half of this
time inside qmd, which means qmd hangs or has models on the CPU. A search reaches qmd
at most twice, so that a query that crashes it cannot keep doing so.

qmd's HTTP server buffers each response until it is complete, so an open
subscriptions/listen stream delivers neither its acknowledgement nor any
notification. Claude Code waits 25 seconds for that acknowledgement while
connecting, and reopens a stream that closes, with a tools/list each time. The
gateway therefore removes listChanged from the capabilities in server/discover
and initialize answers, and Claude Code no longer subscribes. For a client
that subscribes anyway, the gateway empties the request's filter, and qmd
acknowledges and closes the stream at once. qmd's tools do not change while it
runs, so clients lose nothing.

## CONFIGURATION

| Variable | Default or purpose |
| --- | --- |
| BRAIN_REPO | slds-lmu/wintermute-brain-content-slds |
| BRAIN_DIR | /brain/repo |
| BRAIN_CODE_REPO | slds-lmu/wintermute-brain |
| BRAIN_CODE_DIR | /brain/code; copy of the code repository at the latest main |
| BRAIN_POLL | 300 seconds; worker synchronization |
| BRAIN_AUTO_COMPILE | true |
| BRAIN_MODEL | sonnet |
| BRAIN_APP_ID | GitHub App ID |
| BRAIN_APP_INSTALLATION_ID | App installation ID |
| BRAIN_APP_KEY | Mounted PEM path; worker only |
| BRAIN_AUTH_CACHE | /state/auth; private installation-token cache |
| ANTHROPIC_API_KEY | Worker only |
| BRAIN_SEARCH_SERVICE_TOKEN | Shared only by search and compile worker |
| BRAIN_INDEX_POLL | 60 seconds |
| BRAIN_SEARCH_SLOTS | 2; searches running at once |
| BRAIN_SEARCH_LIMIT | 10; searches running or waiting |
| BRAIN_SEARCH_WAIT | 55 seconds; below Claude Code's 60-second header limit |
| BRAIN_CONTROL_WAIT | 30 seconds; calls that need no model, while qmd is down |
| BRAIN_QMD_GPU_MIB | 6000; free GPU memory qmd waits for before loading its models |
| BRAIN_QMD_PORT | 8182 |
| BRAIN_QMD_ENTRY | qmd's dist/cli/qmd.js in the image |
| BRAIN_QMD_POLL | 1 second; check on the qmd process |
| BRAIN_LOG_LEVEL | INFO |
| BRAIN_QMD_STATE | /state/qmd; collection configuration |
| XDG_CACHE_HOME | /cache; qmd database and models |
| QMD_EMBED_PARALLELISM | 1; bounds concurrent model contexts |

The App requires Contents, Pull requests, and Issues write access, plus
Actions read access for merge verification. It is installed on the
code and content repositories. The credential helper and gh wrapper renew installation
tokens before expiry. The worker does not require periodic restarts or a
personal deployment token.

## IMAGE BUILD AND DEPLOYMENT

The server-image workflow tests the server and existing tools, builds a
CUDA 12.6.3 sm70 backend, and publishes:

    ghcr.io/slds-lmu/wintermute-brain:sha-<full-commit>

Only main moves the main image tag. Review branches can publish immutable
builds for deployment without merging their PR. Runtime, tools, plugin,
and dependency changes trigger builds; wiki content changes are synchronized
independently. Registry build cache retains native build stages.

The runtime uses the same CUDA base image as the GPU server's Whisper
image. Node llama.cpp is compiled against that runtime; optional platform
packages containing additional CUDA libraries are omitted. Docker shares
identical layers between images and containers. Build tools remain in the
build stage.

Python packages come from server/requirements.lock, installed with hash checks.
Base images are pinned by digest and CI actions by commit. New versions enter
through server/update-locks.sh, which takes nothing uploaded in the last 3 days:
compromised releases are usually found within hours. A fix of a known vulnerability
may skip that period, as such releases get more attention: check the advisory and
pass --upgrade-package NAME and --exclude-newer-package NAME=<now>. Repeat the
latter on later runs until the release is 3 days old: the script otherwise moves the
package back. The monthly routine passes --upgrade. The direct pins in
server/requirements*.txt move by editing them. The pip step sits below the large qmd
layer, so that a lock update costs hosts a few megabytes.

The CUDA base stays on one digest, because a new one moves every layer. Ubuntu's
security and stable updates come through a layer after the pip step instead; a new
SECURITY_UPDATES date in the Dockerfile rebuilds only that layer and those below it.
NVIDIA's packages, which would offer CUDA 13, are not touched. The infrastructure repository's vulnerability
scan reports when that is due. Still unlocked: the Claude Code and gitleaks
downloads (exact versions, no hash), and Hugging Face model files.

The CMAKE_CUDA_ARCHITECTURES option must be 70 during both build and
runtime: node-llama-cpp includes CMake options in its binary lookup key.
The image sets NODE_LLAMA_CPP_CMAKE_OPTION_CMAKE_CUDA_ARCHITECTURES=70.
Its generic inspect gpu command checks optional prebuilt packages and can
report them missing even when the local CUDA build works. Validate the
selected backend with node /opt/brain/server/check-gpu.mjs.

Modern MCP requests carry protocolVersion, clientCapabilities, and
clientInfo in params._meta under their io.modelcontextprotocol/ keys.
The MCP-Protocol-Version header must match. Older clients use the SDK's
legacy HTTP fallback; the gateway preserves JSON and SSE response types.
Modern requests also set Mcp-Method and, for tool calls, Mcp-Name to
match the JSON-RPC body.

Application changes use an ordinary development branch and review PR.
Content operations continue to use the plugin/tools write path.

## VALIDATION

    python -m pytest server/tests
    python -m unittest discover -s tests
    ruff check --select E4,E7,E9,F,I server

GET /healthz reports gateway health, qmd's state, and whether it is ready. It answers
503 while qmd or the index refresh is failing. It is public, so it omits the indexed
revision, which the log records. Deployment validation must also exercise an
authorized MCP search and a search during OCR.

CI runs Python 3.10, matching Ubuntu 22.04 in the image, and Python 3.12.
Use asyncio.TimeoutError for asyncio deadlines on both versions.
