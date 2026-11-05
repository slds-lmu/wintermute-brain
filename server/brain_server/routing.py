"""Send MCP calls to the GPU or CPU qmd. Searches race; other calls need no model."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable

import httpx
from fastapi.responses import JSONResponse, Response, StreamingResponse

log = logging.getLogger(__name__)

HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length",
}
# Status for a request whose client has gone; nobody reads the response.
CLIENT_CLOSED = 499
STILL_SEARCHING = b": searching\n\n"


class BackendFailed(Exception):
    """A qmd instance could not answer, as opposed to answering with an error."""


@dataclass
class Call:
    method: str
    body: bytes
    headers: dict[str, str]
    discovery: bool = False
    # The JSON-RPC id, when the client also accepts an SSE response.
    event_id: int | str | None = None
    gpu_admitted_at: float | None = None


def _is_search(message: object) -> bool:
    if not isinstance(message, dict) or message.get("method") != "tools/call":
        return False
    params = message.get("params")
    return isinstance(params, dict) and params.get("name") == "query"


def is_search(payload: object) -> bool:
    if isinstance(payload, list):
        return any(_is_search(message) for message in payload)
    return _is_search(payload)


def is_discovery(payload: object) -> bool:
    return isinstance(payload, dict) and payload.get("method") in {"server/discover", "initialize"}


def as_event(response: Response, request_id: int | str) -> bytes:
    """The body of a finished search as the single event of an SSE response."""
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        return response.body
    try:
        message = json.loads(response.body)
    except ValueError:
        message = None
    if not isinstance(message, dict) or "jsonrpc" not in message:
        detail = message.get("detail") if isinstance(message, dict) else None
        message = {
            "jsonrpc": "2.0", "id": request_id,
            "error": {"code": -32000, "message": detail or "Search failed"},
        }
    return b"event: message\ndata: " + json.dumps(message).encode() + b"\n\n"


def without_list_changed(content: bytes) -> bytes:
    """Stop advertising change notifications, so that clients do not subscribe.

    qmd's HTTP server buffers a whole response before sending it, so it can
    deliver no notification. Claude Code would otherwise wait 25 seconds for an
    acknowledgement that never arrives, and reopen a closed stream indefinitely.
    """
    try:
        message = json.loads(content)
        capabilities = message["result"]["capabilities"]
    except (ValueError, KeyError, TypeError):
        return content
    if not isinstance(capabilities, dict):
        return content
    for capability in capabilities.values():
        if isinstance(capability, dict):
            capability.pop("listChanged", None)
    return json.dumps(message).encode()


def without_subscriptions(payload: object, body: bytes) -> bytes:
    """For clients that subscribe anyway: qmd acknowledges an empty filter at once.

    An open subscription would never deliver its acknowledgement, for the reason
    given above. Invalid requests stay unchanged for qmd to reject.
    """
    if not isinstance(payload, dict) or payload.get("method") != "subscriptions/listen":
        return body
    params = payload.get("params")
    if not isinstance(params, dict) or not isinstance(params.get("notifications"), dict):
        return body
    return json.dumps({**payload, "params": {**params, "notifications": {}}}).encode()


class Router:
    def __init__(self, runtime, cpu, client: httpx.AsyncClient) -> None:
        self.runtime = runtime
        self.cpu = cpu
        self.client = client
        # Caddy gives up on the gateway after 300 s.
        self.search_wait = float(os.environ.get("BRAIN_SEARCH_WAIT", "280"))
        self.control_wait = float(os.environ.get("BRAIN_CONTROL_WAIT", "30"))
        self.gpu_search_timeout = float(os.environ.get("BRAIN_GPU_SEARCH_TIMEOUT", "180"))
        # A GPU search normally takes seconds: past this, it may be hanging.
        self.gpu_hedge = float(os.environ.get("BRAIN_GPU_HEDGE", "30"))
        # Searches on the CPU qmd, running or queued, before others fail at once.
        self.cpu_queue_limit = int(os.environ.get("BRAIN_CPU_QUEUE", "4"))
        self.cpu_attempts = 0
        # Claude Code gives up on a request without response headers after 60 s.
        self.answer_wait = float(os.environ.get("BRAIN_ANSWER_WAIT", "20"))
        self.keepalive = float(os.environ.get("BRAIN_KEEPALIVE", "15"))
        self.tick = 0.25

    async def _forward(self, upstream: str, call: Call, timeout: float) -> httpx.Response:
        try:
            response = await self.client.request(
                call.method, upstream + "/mcp", content=call.body, headers=call.headers,
                timeout=timeout,
            )
        except httpx.HTTPError as error:
            raise BackendFailed(type(error).__name__) from error
        if response.status_code >= 500:
            raise BackendFailed(f"qmd answered {response.status_code}")
        return response

    @staticmethod
    def _reply(upstream: httpx.Response, backend: str, discovery: bool = False) -> Response:
        headers = {
            name: value for name, value in upstream.headers.items()
            if name.lower() not in HOP_HEADERS | {"content-encoding"}
        }
        headers["X-Brain-Backend"] = backend
        content = without_list_changed(upstream.content) if discovery else upstream.content
        return Response(content, status_code=upstream.status_code, headers=headers)

    def _unavailable(self, detail: str, retry_after: int) -> JSONResponse:
        return JSONResponse(
            {"detail": detail, "state": self.runtime.state},
            status_code=503, headers={"Retry-After": str(retry_after)},
        )

    async def control(self, call: Call) -> Response:
        """Run a call that needs no model, independently of the GPU's state."""
        deadline = time.monotonic() + self.control_wait
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self._unavailable("Search backend unavailable", 5)
            try:
                if self.cpu.available.is_set():
                    upstream = await self._forward(self.cpu.upstream, call, remaining)
                    return self._reply(upstream, "cpu", call.discovery)
                if self.runtime.ready.is_set():
                    async with self.runtime.admission():
                        upstream = await self._forward(self.runtime.upstream, call, remaining)
                    return self._reply(upstream, "gpu", call.discovery)
            except BackendFailed as error:
                # The CPU qmd restarts within a second after an aborted search.
                log.info("Retrying a call without model use: %s", error)
            await asyncio.sleep(0.1)

    async def _gpu_attempt(self, call: Call, delay: float = 0) -> httpx.Response:
        if delay:
            await asyncio.sleep(delay)
        async with self.runtime.admission():
            call.gpu_admitted_at = time.monotonic()
            return await self._forward(self.runtime.upstream, call, self.gpu_search_timeout)

    async def _cpu_attempt(self, call: Call) -> httpx.Response:
        async with self.cpu.search_slot:
            await self.cpu.available.wait()
            try:
                return await self._forward(self.cpu.upstream, call, self.search_wait)
            except asyncio.CancelledError:
                # Disconnecting from qmd does not stop its search.
                log.info("Abandoning a CPU search: killing the CPU qmd")
                self.cpu.abort()
                raise

    async def search(self, call: Call, disconnected: Callable[[], Awaitable[bool]]) -> Response:
        """Answer plainly if that is quick, otherwise as an SSE event when ready.

        qmd cannot stream, so response headers normally wait for the answer. A
        search on the CPU can take longer than clients wait for those headers.
        """
        race = asyncio.create_task(self._race(call, disconnected))
        if call.event_id is None:
            return await race
        done, _ = await asyncio.wait({race}, timeout=self.answer_wait)
        if done:
            return race.result()
        return StreamingResponse(
            self._events(race, call.event_id),
            media_type="text/event-stream",
            # no-transform: Caddy would otherwise buffer the stream to compress it.
            headers={"Cache-Control": "no-cache, no-transform"},
        )

    async def _events(self, race: asyncio.Task, request_id: int | str) -> AsyncIterator[bytes]:
        try:
            yield STILL_SEARCHING
            while True:
                done, _ = await asyncio.wait({race}, timeout=self.keepalive)
                if done:
                    break
                yield STILL_SEARCHING
            response = race.result()
            if response.status_code != CLIENT_CLOSED:
                yield as_event(response, request_id)
        finally:
            # Also reached when the client disconnects from the stream.
            race.cancel()

    def _start_cpu_attempt(self, call: Call) -> asyncio.Task:
        self.cpu_attempts += 1
        task = asyncio.create_task(self._cpu_attempt(call))

        def finished(_: asyncio.Task) -> None:
            self.cpu_attempts -= 1

        task.add_done_callback(finished)
        return task

    async def _race(self, call: Call, disconnected: Callable[[], Awaitable[bool]]) -> Response:
        """Run a search on the GPU; while it is taken, race the CPU against it."""
        started = time.monotonic()
        deadline = started + self.search_wait
        gpu = asyncio.create_task(self._gpu_attempt(call))
        cpu = None
        cpu_failures = 0
        try:
            while True:
                pending = {task for task in (gpu, cpu) if task is not None}
                done, _ = await asyncio.wait(
                    pending, timeout=self.tick, return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    backend = "gpu" if task is gpu else "cpu"
                    try:
                        response = task.result()
                    except BackendFailed as error:
                        log.warning("Search failed on the %s qmd: %s", backend, error)
                        if task is gpu:
                            # qmd was stopped or crashed: wait for the next
                            # admission and let the CPU take over meanwhile.
                            call.gpu_admitted_at = None
                            gpu = asyncio.create_task(self._gpu_attempt(call, delay=1))
                        else:
                            cpu_failures += 1
                            cpu = None
                        continue
                    log.info("Search answered by the %s qmd in %.1f s", backend, time.monotonic() - started)
                    return self._reply(response, backend)
                now = time.monotonic()
                gpu_running = call.gpu_admitted_at is not None
                if cpu is None and cpu_failures < 3 and (
                    not gpu_running or now - call.gpu_admitted_at >= self.gpu_hedge
                ):
                    if self.cpu_attempts < self.cpu_queue_limit:
                        cpu = self._start_cpu_attempt(call)
                    elif not gpu_running:
                        # Let the client fall back at once rather than after minutes.
                        log.warning("CPU search queue is full")
                        return self._unavailable("Search is busy", 30)
                if now >= deadline:
                    log.warning("Search gave up after %.0f s", now - started)
                    return self._unavailable("Search is waiting for a free backend", 30)
                if await disconnected():
                    return Response(status_code=CLIENT_CLOSED)
        finally:
            attempts = [task for task in (gpu, cpu) if task is not None]
            for task in attempts:
                task.cancel()
            await asyncio.gather(*attempts, return_exceptions=True)
