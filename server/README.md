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
decisions are cached for five minutes using token hashes; plaintext tokens
are forwarded only to GitHub. The qmd HTTP listener is container-local.

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

qmd holds an exclusive flock on BRAIN_GPU_LOCK while its process and model
weights are resident. GPU callers publish a locked *.request file under
the adjacent requests directory before waiting for the same lock. The
request file remains locked until GPU use finishes.

The coordinator checks live request files and Redis RQ queues, intermediate
queues, and non-expired started-job entries. It drains active MCP requests,
terminates qmd, waits for process exit, then releases the flock. The qmd
child inherits the descriptor so a coordinator failure cannot prematurely
release the lock while the child still uses the GPU.

qmd stays unloaded throughout an OCR batch. After all watched queues and
requesters are idle for BRAIN_GPU_QUIET seconds, it reacquires the lock,
updates the index and pending embeddings, restarts qmd, and warms the
models. Orphaned request files are removed after their flock is released.
Redis failures release the GPU conservatively. Whisper's HTTP server stays
resident; its batch and memory-recovery lock requests also trigger handoff.

Search requests wait up to BRAIN_SEARCH_WAIT seconds for GPU availability,
then receive HTTP 503 with Retry-After. The normal clone/index fallback
still applies. Running GPU operations finish before a handoff.

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
| BRAIN_INDEX_POLL | 60 seconds |
| BRAIN_SEARCH_WAIT | 60 seconds |
| BRAIN_QMD_STATE | /state/qmd; collection configuration |
| XDG_CACHE_HOME | /cache; qmd database and models |
| QMD_EMBED_PARALLELISM | 1; bounds concurrent model contexts |

The App requires Contents, Pull requests, and Issues write access, plus
Actions read access for merge verification. It is installed on this
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

Application changes use an ordinary development branch and review PR.
Content operations continue to use the pinned plugin/tools write path.

## VALIDATION

    python -m pytest server/tests
    python -m unittest discover -s tests
    ruff check --select E4,E7,E9,F,I server

GET /healthz reports gateway health, qmd state, and indexed revision.
The gateway remains healthy while yielding the GPU. Deployment validation
must also exercise an authorized MCP search and a multi-job GPU handoff.
