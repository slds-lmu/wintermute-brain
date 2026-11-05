"""Run qmd on the GPU and on the CPU, yielding the GPU to queued workloads."""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import signal
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import redis.asyncio as redis
import yaml

log = logging.getLogger(__name__)
GPU_CHECK = Path(__file__).resolve().parents[1] / "check-gpu.mjs"


def qmd_server(port: int) -> list[str]:
    """The server itself: qmd's launcher would be a parent that exits first."""
    entry = os.environ.get("BRAIN_QMD_ENTRY", "/opt/qmd/node_modules/@tobilu/qmd/dist/cli/qmd.js")
    return ["node", entry, "mcp", "--http", "--host", "127.0.0.1", "--port", str(port)]


def live_gpu_requests(directory: Path) -> bool:
    """Request files are locked for the caller's entire wait and GPU use."""
    live = False
    for path in directory.glob("*.request"):
        try:
            # Read mode: a request that just finished must not be recreated.
            with path.open("rb") as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    live = True
                else:
                    path.unlink(missing_ok=True)
        except FileNotFoundError:
            continue
    return live


class QueueDemand:
    def __init__(self, client, queues: list[str]) -> None:
        self.client = client
        self.queues = queues

    async def busy(self) -> bool:
        pipeline = self.client.pipeline(transaction=True)
        for name in self.queues:
            pipeline.llen("rq:queue:" + name)
            pipeline.llen("rq:queue:" + name + ":intermediate")
            pipeline.zcount("rq:wip:" + name, time.time(), "+inf")
        return any(await pipeline.execute())


class QmdRuntime:
    def __init__(self, demand=None) -> None:
        self.repo = Path(os.environ.get("BRAIN_DIR", "/brain/repo"))
        self.state_dir = Path(os.environ.get("BRAIN_QMD_STATE", "/state/qmd"))
        self.lock_path = Path(os.environ.get("BRAIN_GPU_LOCK", "/data/locks/gpu.lock"))
        self.request_dir = self.lock_path.parent / "requests"
        self.upstream = os.environ.get("QMD_UPSTREAM", "http://127.0.0.1:8182")
        self.poll = float(os.environ.get("BRAIN_GPU_POLL", "0.5"))
        self.quiet = float(os.environ.get("BRAIN_GPU_QUIET", "5"))
        self.refresh_interval = float(os.environ.get("BRAIN_INDEX_POLL", "60"))
        self.drain_timeout = float(os.environ.get("BRAIN_GPU_DRAIN", "30"))
        self.ready = asyncio.Event()
        self.idle = asyncio.Event()
        self.idle.set()
        self.active = 0
        self.state = "starting"
        self.process = None
        self.lock = None
        self.stopping = False
        self.cooldown_until = 0.0
        self.last_refresh = 0.0
        self.revision = ""
        self.failing = False
        self.client = httpx.AsyncClient(timeout=180)
        self.redis = None
        if demand is None:
            self.redis = redis.from_url(
                os.environ.get("BRAIN_REDIS_URL", "redis://redis:6379/0"),
                socket_timeout=5, socket_connect_timeout=5,
            )
            demand = QueueDemand(
                self.redis, os.environ.get("BRAIN_GPU_QUEUES", "mineru,whisper").split(","),
            )
        self.demand = demand

    def status(self) -> dict:
        return {"state": self.state, "ready": self.ready.is_set(), "failing": self.failing}

    def _acquire_gpu(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.request_dir.mkdir(exist_ok=True)
        self.lock = self.lock_path.open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            self.lock = None
            return False
        return True

    async def busy(self) -> bool:
        return (
            await asyncio.to_thread(live_gpu_requests, self.request_dir)
            or await self.demand.busy()
        )

    def repository_ready(self) -> bool:
        return (self.repo / ".git" / "brain-ready").exists()

    async def drained(self) -> bool:
        try:
            await asyncio.wait_for(self.idle.wait(), self.drain_timeout)
        except asyncio.TimeoutError:
            return False
        return True

    @asynccontextmanager
    async def admission(self):
        while True:
            await self.ready.wait()
            if self.ready.is_set():
                self.active += 1
                self.idle.clear()
                break
        try:
            yield
        finally:
            self.active -= 1
            if not self.active:
                self.idle.set()

    async def pause(self, state: str = "paused") -> None:
        self.ready.clear()
        self.state = state
        # A search still running at the deadline fails over to the CPU qmd.
        drained = await self.drained()
        if not drained:
            log.warning("qmd searches still active after %.0f s; stopping qmd", self.drain_timeout)
        if self.process is not None:
            if self.process.returncode is None:
                os.killpg(self.process.pid, signal.SIGTERM if drained else signal.SIGKILL)
                try:
                    await asyncio.wait_for(self.process.wait(), 10)
                except asyncio.TimeoutError:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    await self.process.wait()
            self.process = None
        if self.lock is not None:
            fcntl.flock(self.lock, fcntl.LOCK_UN)
            self.lock.close()
            self.lock = None

    def configure(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "collections": {
                "wiki": {
                    "path": str(self.repo / "wiki"), "pattern": "**/*.md",
                    "ignore": ["**/index.md", "**/index-*.md"],
                    "context": {"/": "Compiled SLDS group wiki pages."},
                },
                "raw": {
                    "path": str(self.repo / "raw"), "pattern": "**/*.md",
                    "context": {"/": "Original source text; distinguish sources from compiled wiki pages."},
                },
            },
        }
        # Atomic: the CPU qmd may start while the GPU qmd is being configured.
        temporary = self.state_dir / "index.yml.tmp"
        temporary.write_text(yaml.safe_dump(config))
        temporary.replace(self.state_dir / "index.yml")

    def environment(self) -> dict:
        environment = {k: v for k, v in os.environ.items() if k != "BRAIN_SEARCH_SERVICE_TOKEN"}
        environment.update(
            QMD_CONFIG_DIR=str(self.state_dir),
            # Set by qmd's launcher for its MCP servers.
            LLAMA_LOG_LEVEL="error", GGML_LOG_LEVEL="error", GGML_BACKEND_SILENT="1",
        )
        return environment

    async def command(self, *arguments: str, timeout: float = 180) -> str:
        process = await asyncio.create_subprocess_exec(
            *arguments, env=self.environment(),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            pass_fds=(self.lock.fileno(),) if self.lock else (),
            start_new_session=True,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout)
        except BaseException:
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
            raise
        if process.returncode:
            raise RuntimeError(f"{arguments[0]} failed ({process.returncode}): {output.decode()[-1500:]}")
        return output.decode()

    async def check_gpu(self) -> None:
        """qmd falls back to its CPU backend without any error when CUDA fails."""
        await self.command("node", str(GPU_CHECK))

    async def refresh(self) -> None:
        # Searches continue meanwhile: qmd supports this on one index.
        if not self.ready.is_set():
            self.state = "indexing"
        # Record the revision before scanning. A pull during embedding must
        # remain visible as a change on the next refresh.
        revision = (await self.command(
            "git", "-C", str(self.repo), "rev-parse", "HEAD",
        )).strip()
        if revision != self.revision:
            await self.command("qmd", "update")
        await self.command(
            "qmd", "embed", "--timeout", "1", "--max-docs-per-batch", "8",
            timeout=180,
        )
        if revision != self.revision:
            log.info("Indexed content revision %s", revision)
        self.revision = revision
        self.last_refresh = time.monotonic()

    async def warm(self) -> None:
        self.state = "warming"
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if self.process.returncode is not None:
                raise RuntimeError("qmd exited during startup")
            try:
                response = await self.client.get(self.upstream + "/health", timeout=2)
                response.raise_for_status()
                break
            except httpx.HTTPError:
                await asyncio.sleep(0.25)
        else:
            raise RuntimeError("qmd startup timed out")
        # A fresh query loads expansion, embedding, and reranking models even
        # after a previous process populated the persistent query cache.
        response = await self.client.post(
            self.upstream + "/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/call",
                "Mcp-Name": "query",
            },
            json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                    "io.modelcontextprotocol/clientInfo": {"name": "brain-warmup", "version": "1"},
                }, "name": "query", "arguments": {
                    "query": "SLDS research wiki " + uuid.uuid4().hex[:8],
                    "limit": 1, "candidateLimit": 1,
                }},
            },
        )
        response.raise_for_status()
        result = response.json()
        if "error" in result or result.get("result", {}).get("isError"):
            raise RuntimeError("qmd warmup failed: " + json.dumps(result)[:1000])

    async def step(self) -> None:
        if await self.busy():
            if self.process or self.lock:
                log.info("GPU requested; draining qmd and releasing models")
            await self.pause()
            self.cooldown_until = time.monotonic() + self.quiet
            return
        if not self.repository_ready():
            self.state = "waiting_for_repository"
            return
        if self.process and self.process.returncode is not None:
            await self.pause("restarting")
        if self.process is None:
            if (
                time.monotonic() < self.cooldown_until
                or not await asyncio.to_thread(self._acquire_gpu)
            ):
                self.state = "paused"
                return
            # Recheck queue state after acquiring the lock to close the handoff race.
            if await self.busy():
                await self.pause()
                return
            self.configure()
            await self.check_gpu()
            await self.refresh()
            if await self.busy():
                await self.pause()
                return
            self.process = await asyncio.create_subprocess_exec(
                *qmd_server(8182),
                env=self.environment(), pass_fds=(self.lock.fileno(),),
                start_new_session=True,
            )
            await self.warm()
            log.info("qmd models warm")
        elif time.monotonic() - self.last_refresh >= self.refresh_interval:
            await self.refresh()
        if await self.busy():
            await self.pause()
        else:
            self.state = "ready"
            self.failing = False
            self.ready.set()

    async def _pause_after_error(self) -> None:
        try:
            await self.pause("error")
        except Exception:
            # The loop must survive to retry: a dead coordinator would leave
            # the process up with search permanently unavailable.
            log.exception("Could not release the GPU; retrying")

    async def run(self) -> None:
        try:
            while not self.stopping:
                try:
                    await self.step()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("qmd coordinator failed; releasing the GPU")
                    self.failing = True
                    await self._pause_after_error()
                    await asyncio.sleep(5)
                await asyncio.sleep(self.poll)
        finally:
            await self.pause("stopped")
            await self.client.aclose()
            if self.redis:
                await self.redis.aclose()


class CpuQmd:
    """A CPU-only qmd on the same index, supervised so that it can be killed.

    It serves every call that needs no model and races the GPU qmd for
    searches while the GPU is taken. qmd has no way to cancel a running search,
    and the search keeps its threads after the client disconnects. Killing the
    process is the only abort, which is why searches run one at a time.
    """

    def __init__(self, runtime: QmdRuntime) -> None:
        self.runtime = runtime
        self.port = int(os.environ.get("BRAIN_CPU_PORT", "8183"))
        self.upstream = f"http://127.0.0.1:{self.port}"
        self.nice = os.environ.get("BRAIN_CPU_NICE", "19")
        self.parallelism = os.environ.get("BRAIN_CPU_PARALLELISM", "2")
        # Assumes two hardware threads per core, as on the V100 VM. qmd's default
        # of one thread per vCPU runs query expansion about five times slower.
        self.expand_threads = os.environ.get(
            "BRAIN_CPU_EXPAND_THREADS", str(max(1, (os.cpu_count() or 2) // 2)),
        )
        self.startup_timeout = float(os.environ.get("BRAIN_CPU_STARTUP", "60"))
        self.health_interval = float(os.environ.get("BRAIN_CPU_HEALTH_INTERVAL", "30"))
        self.available = asyncio.Event()
        self.down_since = time.monotonic()
        self.search_slot = asyncio.Semaphore(1)
        self.process = None
        self.aborted = False
        self.client = httpx.AsyncClient(timeout=2)

    def environment(self) -> dict:
        return dict(
            self.runtime.environment(),
            QMD_FORCE_CPU="1",
            QMD_LLAMA_GPU="false",
            QMD_EMBED_PARALLELISM=self.parallelism,
            QMD_EXPAND_THREADS=self.expand_threads,
            CUDA_VISIBLE_DEVICES="",
        )

    def down_for(self) -> float:
        return 0 if self.available.is_set() else time.monotonic() - self.down_since

    def abort(self) -> None:
        """Stop all work now. Synchronous, so that a cancelled task can call it."""
        if self.available.is_set():
            self.down_since = time.monotonic()
            self.available.clear()
        if self.process is not None and self.process.returncode is None:
            self.aborted = True
            os.killpg(self.process.pid, signal.SIGKILL)

    async def _start(self) -> None:
        self.runtime.configure()
        # No pass_fds: this process must never share the GPU lock.
        self.process = await asyncio.create_subprocess_exec(
            "nice", "-n", self.nice, *qmd_server(self.port),
            env=self.environment(), start_new_session=True,
        )
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self.process.returncode is not None:
                raise RuntimeError("CPU qmd exited during startup")
            try:
                response = await self.client.get(self.upstream + "/health")
                response.raise_for_status()
            except httpx.HTTPError:
                await asyncio.sleep(0.05)
            else:
                self.available.set()
                return
        raise RuntimeError("CPU qmd startup timed out")

    async def _watch(self) -> None:
        """Return when the process has exited or stopped answering."""
        failures = 0
        while failures < 3:
            try:
                await asyncio.wait_for(self.process.wait(), self.health_interval)
                return
            except asyncio.TimeoutError:
                pass
            try:
                response = await self.client.get(self.upstream + "/health", timeout=10)
                response.raise_for_status()
                failures = 0
            except httpx.HTTPError:
                failures += 1
        log.warning("CPU qmd stopped answering; restarting")

    async def run(self) -> None:
        try:
            while True:
                if not self.runtime.repository_ready():
                    await asyncio.sleep(1)
                    continue
                self.aborted = False
                try:
                    await self._start()
                    await self._watch()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("CPU qmd failed")
                self.abort()
                if self.process is not None:
                    await self.process.wait()
                    self.process = None
                if not self.aborted:
                    log.warning("CPU qmd stopped unexpectedly; restarting")
                    await asyncio.sleep(5)
        finally:
            self.abort()
            if self.process is not None:
                await self.process.wait()
            await self.client.aclose()
