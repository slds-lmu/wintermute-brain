"""Run one qmd on the GPU and keep its index current."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import signal
import time
import uuid
from pathlib import Path

import httpx
import yaml

log = logging.getLogger(__name__)

# qmd reports a lack of GPU memory only here and answers with no or unranked
# results. The next query after that crashes it (SIGILL), so qmd gets restarted.
BROKEN_SEARCH = re.compile(r"Failed to create any embedding context|Reranker unavailable")
# A skipped query expansion costs some recall but the models stay usable.
DEGRADED_SEARCH = re.compile(r"query expansion failed: InsufficientMemoryError")
# qmd logs each request with its query text, and has no setting to stop that.
REQUEST_LINE = re.compile(r"^\d\d:\d\d:\d\d\.\d+ [A-Z]+ /")


def qmd_server(port: int) -> list[str]:
    """The server itself: qmd's launcher would be a parent that exits first."""
    entry = os.environ.get("BRAIN_QMD_ENTRY", "/opt/qmd/node_modules/@tobilu/qmd/dist/cli/qmd.js")
    return ["node", entry, "mcp", "--http", "--host", "127.0.0.1", "--port", str(port)]


class QmdRuntime:
    def __init__(self) -> None:
        self.repo = Path(os.environ.get("BRAIN_DIR", "/brain/repo"))
        self.state_dir = Path(os.environ.get("BRAIN_QMD_STATE", "/state/qmd"))
        self.port = int(os.environ.get("BRAIN_QMD_PORT", "8182"))
        self.upstream = f"http://127.0.0.1:{self.port}"
        self.poll = float(os.environ.get("BRAIN_QMD_POLL", "1"))
        self.refresh_interval = float(os.environ.get("BRAIN_INDEX_POLL", "60"))
        self.ready = asyncio.Event()
        self.state = "starting"
        self.process = None
        self.log_reader = None
        self.stopping = False
        self.failing = False
        self.refresh_failing = False
        # Searches compare this before and after their call to qmd.
        self.broken_searches = 0
        self.restart_needed = False
        self.revision = ""
        self.client = httpx.AsyncClient(timeout=180)

    def status(self) -> dict:
        return {
            "state": self.state, "ready": self.ready.is_set(),
            "failing": self.failing or self.refresh_failing,
        }

    def repository_ready(self) -> bool:
        return (self.repo / ".git" / "brain-ready").exists()

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

    async def watch_log(self, stream) -> None:
        # This reader must outlive any output: qmd blocks once the pipe is full.
        while True:
            try:
                raw = await stream.readline()
            except ValueError:
                # Longer than the stream's buffer; readline has dropped it.
                continue
            if not raw:
                return
            line = raw.decode(errors="replace").rstrip()
            if REQUEST_LINE.match(line):
                continue
            if BROKEN_SEARCH.search(line):
                self.broken_searches += 1
                self.restart_needed = True
                log.error("qmd lacks GPU memory; restarting it: %s", line)
            elif DEGRADED_SEARCH.search(line):
                log.warning("qmd lacks GPU memory for query expansion and searched without it")
            else:
                print(line, flush=True)

    async def start(self) -> None:
        self.state = "warming"
        self.restart_needed = False
        self.configure()
        await self.refresh()
        self.process = await asyncio.create_subprocess_exec(
            *qmd_server(self.port),
            env=self.environment(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        self.log_reader = asyncio.create_task(self.watch_log(self.process.stdout))
        await self.warm()
        log.info("qmd models warm")

    async def warm(self) -> None:
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
        # Loads all models, which also shows now whether they fit.
        broken = self.broken_searches
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
        # Its log line can arrive after the response.
        await asyncio.sleep(0.05)
        if self.broken_searches != broken:
            raise RuntimeError("qmd lacks GPU memory for its models")

    async def stop(self, state: str) -> None:
        self.ready.clear()
        self.state = state
        if self.process is not None:
            if self.process.returncode is None:
                # SIGTERM can spend seconds disposing models; state is in SQLite (WAL).
                os.killpg(self.process.pid, signal.SIGKILL)
            await self.process.wait()
            self.process = None
        if self.log_reader is not None:
            self.log_reader.cancel()
            await asyncio.gather(self.log_reader, return_exceptions=True)
            self.log_reader = None

    async def step(self) -> None:
        if not self.repository_ready():
            self.state = "waiting_for_repository"
            return
        if self.process is not None and self.process.returncode is not None:
            log.warning("qmd exited with %s; restarting", self.process.returncode)
            await self.stop("restarting")
        elif self.process is not None and self.restart_needed:
            await self.stop("restarting")
        if self.process is None:
            await self.start()
            self.failing = False
        self.state = "ready"
        self.ready.set()

    async def refresh_loop(self) -> None:
        """Update the index beside the running qmd, which serves searches meanwhile."""
        while True:
            await asyncio.sleep(self.refresh_interval)
            if not self.ready.is_set():
                continue
            try:
                await self.refresh()
                self.refresh_failing = False
            except Exception:
                # The current index stays usable; /healthz reports the failure.
                log.exception("Index refresh failed")
                self.refresh_failing = True

    async def run(self) -> None:
        refresher = asyncio.create_task(self.refresh_loop())
        try:
            while not self.stopping:
                try:
                    await self.step()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("qmd failed")
                    self.failing = True
                    await self.stop("error")
                    await asyncio.sleep(5)
                await asyncio.sleep(self.poll)
        finally:
            refresher.cancel()
            await asyncio.gather(refresher, return_exceptions=True)
            await self.stop("stopped")
            await self.client.aclose()
