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
qmd HTTP listeners are container-local.

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
content clone if missing, polls main every five minutes, checks out the
code release named by .brain-version into BRAIN_CODE_DIR, and compiles the
derived backlog using that release's plugin/tools. The code checkout is
shallow and fetches the selected tag. Set BRAIN_AUTO_COMPILE=false to retain synchronization
without running the agent. BRAIN_QMD is empty: indexing belongs to search.
Search waits for the worker's initial checkout marker before opening the
repository. Text indexing runs when main changes; pending embeddings are
resumed independently without clearing query caches on every poll.

Keep the clone, qmd SQLite database, and model cache on a local filesystem
with working POSIX locks. The database and models are derived state.
Monitor their space use together with Docker storage. The server clone
fetches LFS files; GitHub remains the authoritative content store.

## GPU HANDOFF

The GPU qmd holds an exclusive flock on BRAIN_GPU_LOCK while its process
runs. qmd unloads its models after five idle minutes, by a fixed setting in
its createStore, and reloads them for the next search in about ten seconds.
Keep the lock directory on a local filesystem: the coordinator polls it twice
a second, and flock needs no network. GPU callers publish a locked *.request
file under
the adjacent requests directory before waiting for the same lock. The
request file remains locked until GPU use finishes.

The coordinator checks live request files and Redis RQ queues, intermediate
queues, and non-expired started-job entries. It drains active searches for
up to BRAIN_GPU_DRAIN seconds, stops qmd, waits for process exit, then
releases the flock. A search still running at that deadline is killed with
qmd and continues on the CPU qmd. The qmd child inherits the descriptor so a
coordinator failure cannot prematurely release the lock while the child
still uses the GPU.

qmd stays unloaded throughout an OCR batch. After all watched queues and
requesters are idle for BRAIN_GPU_QUIET seconds, it reacquires the lock,
updates the index and pending embeddings, restarts qmd, and warms the
models. Orphaned request files are removed after their flock is released.
Redis failures release the GPU conservatively. Whisper's HTTP server stays
resident; its batch and memory-recovery lock requests also trigger handoff.

## CPU QMD AND ROUTING

A second qmd process runs with QMD_FORCE_CPU on the same index and model
files, at nice 19 and without access to the GPU lock. It needs about 50 MB
while idle and about 6 GB with its models loaded, which it unloads after five
idle minutes. The image carries its backend, the locked
@node-llama-cpp/linux-x64 prebuilt.

| Call | Handling |
| --- | --- |
| tools/call query | GPU qmd if available, otherwise a race (below) |
| subscriptions/listen | CPU qmd, with an empty notification filter |
| server/discover, initialize | CPU qmd, with listChanged removed from the answer |
| Everything else | CPU qmd; GPU qmd only while the CPU qmd restarts |

Only query uses models: get, multi_get, status, and discovery read SQLite.
Those calls take no GPU admission, so they work and do not delay a handoff
in any GPU state.

A search that gets no GPU admission within BRAIN_CPU_GRACE seconds starts
on the CPU qmd as well, while it keeps waiting for the GPU. The grace period
keeps index refreshes, which close admission for a fraction of a second,
from starting CPU work. Responses are returned only once complete, so the
first complete response wins and the other attempt is abandoned. The answer
carries X-Brain-Backend. After BRAIN_SEARCH_WAIT seconds without an answer,
the client receives 503 with Retry-After. The clone/index fallback applies.

Claude Code abandons a request after 60 seconds without response headers,
unless MCP_TOOL_TIMEOUT or the server's timeout setting raises that limit, and
qmd sends none before its answer is complete. A search still running after
BRAIN_ANSWER_WAIT seconds therefore receives 200 with text/event-stream
headers, a comment line every BRAIN_KEEPALIVE seconds, and finally the answer
as one event. At the deadline this stream carries a JSON-RPC error in place of
the 503. Cache-Control: no-transform keeps Caddy's encode from buffering it.
A client that does not accept text/event-stream gets a plain response at the
end. Claude Code 2.1.318 accepted such an answer after 248 seconds.

The CPU qmd runs one search at a time. qmd cannot cancel a search, and one
keeps its threads after its client has gone. Abandoning a running search,
because the GPU answered first or the client disconnected, therefore kills
the process with SIGKILL. The supervisor restarts it in under a second, and
calls arriving meanwhile retry. An abandoned GPU search runs to completion
because reloading its models would cost more. Attempts share qmd's persistent
LLM cache in SQLite, so an expansion finished on the CPU also serves the GPU.

CPU and GPU use the same models and settings, and expansion sampling is
random on both. Measurements on the V100 VM (20 vCPUs, Xeon Gold 6148, 13
candidates) follow; a GPU search takes 2-3 seconds, or about 10 seconds when
its models have to load first.

| CPU load from other processes at nice 0 | CPU search | Expansion | Reranking |
| --- | --- | --- | --- |
| None | 18-20 s | 2-8 s | 13-16 s |
| 10 busy processes | 58-72 s | 10-15 s | 41-49 s |
| 20 busy processes | 88-116 s | 37-60 s | 47-52 s |

Reranking time grows with the number of candidates, up to 40. Expansion stops
at 600 tokens, about 30 seconds on an idle CPU, or after qmd's limit of 300
seconds, in which case qmd searches for the original query alone.

Thread counts matter on this CPU. Generation yields 21.8 tokens per second
with 10 threads and 4.6 with 20, the number qmd uses by default, so
BRAIN_CPU_EXPAND_THREADS defaults to half the vCPUs and patch-qmd.sh adds the
setting to qmd in the image. Two reranking contexts of 10 threads each are
faster than one of 20 or four of 5, because qmd activates only one context per
10 candidates. Do not restrict the container with a cpuset: llama.cpp would
still start one thread per vCPU, and a search took 432 seconds on 8 of the 20.

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
| BRAIN_CODE_DIR | /brain/code; checkout of the content's pinned code release |
| BRAIN_POLL | 300 seconds; worker synchronization |
| BRAIN_AUTO_COMPILE | true |
| BRAIN_MODEL | sonnet |
| BRAIN_APP_ID | GitHub App ID |
| BRAIN_APP_INSTALLATION_ID | App installation ID |
| BRAIN_APP_KEY | Mounted PEM path; worker only |
| BRAIN_AUTH_CACHE | /state/auth; private installation-token cache |
| ANTHROPIC_API_KEY | Worker only |
| BRAIN_SEARCH_SERVICE_TOKEN | Shared only by search and compile worker |
| BRAIN_GPU_LOCK | /data/locks/gpu.lock |
| BRAIN_GPU_QUEUES | mineru,whisper |
| BRAIN_REDIS_URL | redis://redis:6379/0 |
| BRAIN_GPU_POLL | 0.5 seconds |
| BRAIN_GPU_QUIET | 5 seconds |
| BRAIN_GPU_DRAIN | 30 seconds; wait for active searches before stopping qmd |
| BRAIN_INDEX_POLL | 60 seconds |
| BRAIN_SEARCH_WAIT | 280 seconds; below Caddy's 300-second header limit |
| BRAIN_ANSWER_WAIT | 20 seconds; switch to an event stream after this time |
| BRAIN_KEEPALIVE | 15 seconds; comment lines on that stream |
| BRAIN_GPU_SEARCH_TIMEOUT | 180 seconds |
| BRAIN_CONTROL_WAIT | 30 seconds; calls that need no model |
| BRAIN_CPU_GRACE | 1 second; GPU wait before a search also starts on the CPU |
| BRAIN_CPU_PARALLELISM | 2; reranking contexts of the CPU qmd, sharing all vCPUs |
| BRAIN_CPU_EXPAND_THREADS | Half the vCPUs; query expansion threads of the CPU qmd |
| BRAIN_CPU_NICE | 19 |
| BRAIN_CPU_PORT | 8183 |
| BRAIN_CPU_STARTUP | 60 seconds |
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
build stage. The CPU backend has its own stage and 28 MB layer, verified
against the lock file, so that the native build stage stays cached. Keep it
that way: changing package.json rebuilds that stage and makes every host
download its large layers again. The build fails if the backend cannot load.

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
Content operations continue to use the pinned plugin/tools write path.

## VALIDATION

    python -m pytest server/tests
    python -m unittest discover -s tests
    ruff check --select E4,E7,E9,F,I server

GET /healthz reports gateway health, qmd state, and indexed revision.
The gateway remains healthy while yielding the GPU. Deployment validation
must also exercise an authorized MCP search and a multi-job GPU handoff.

CI runs Python 3.10, matching Ubuntu 22.04 in the image, and Python 3.12.
Use asyncio.TimeoutError for asyncio deadlines on both versions.
