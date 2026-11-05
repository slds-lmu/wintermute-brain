"""Keep qmd warm and yield its GPU allocation to queued GPU workloads."""

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


def live_gpu_requests(directory: Path) -> bool:
    """Request files are locked for the caller's entire wait and GPU use."""
    live = False
    for path in directory.glob("*.request"):
        try:
            with path.open("a") as handle:
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
        self.wait_timeout = float(os.environ.get("BRAIN_SEARCH_WAIT", "60"))
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
        self.client = httpx.AsyncClient(timeout=180)
        self.redis = None
        if demand is None:
            self.redis = redis.from_url(os.environ.get("BRAIN_REDIS_URL", "redis://redis:6379/0"))
            demand = QueueDemand(
                self.redis, os.environ.get("BRAIN_GPU_QUEUES", "mineru,whisper").split(","),
            )
        self.demand = demand

    def status(self) -> dict:
        return {"state": self.state, "ready": self.ready.is_set(), "revision": self.revision}

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
        return live_gpu_requests(self.request_dir) or await self.demand.busy()

    @asynccontextmanager
    async def admission(self):
        deadline = time.monotonic() + self.wait_timeout
        while True:
            await asyncio.wait_for(self.ready.wait(), max(0.001, deadline - time.monotonic()))
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
        await self.idle.wait()
        if self.process is not None:
            if self.process.returncode is None:
                os.killpg(self.process.pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(self.process.wait(), 30)
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
        (self.state_dir / "index.yml").write_text(yaml.safe_dump(config))

    def environment(self) -> dict:
        return dict(os.environ, QMD_CONFIG_DIR=str(self.state_dir))

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

    async def refresh(self) -> None:
        self.ready.clear()
        await self.idle.wait()
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
        if not (self.repo / ".git" / "brain-ready").exists():
            self.state = "waiting_for_repository"
            return
        if self.process and self.process.returncode is not None:
            await self.pause("restarting")
        if self.process is None:
            if time.monotonic() < self.cooldown_until or not self._acquire_gpu():
                self.state = "paused"
                return
            # Recheck queue state after acquiring the lock to close the handoff race.
            if await self.busy():
                await self.pause()
                return
            self.configure()
            await self.refresh()
            if await self.busy():
                await self.pause()
                return
            self.process = await asyncio.create_subprocess_exec(
                "qmd", "mcp", "--http", "--host", "127.0.0.1", "--port", "8182",
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
            self.ready.set()

    async def run(self) -> None:
        try:
            while not self.stopping:
                try:
                    await self.step()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("qmd coordinator failed; releasing the GPU")
                    await self.pause("error")
                    await asyncio.sleep(5)
                await asyncio.sleep(self.poll)
        finally:
            await self.pause("stopped")
            await self.client.aclose()
            if self.redis:
                await self.redis.aclose()
