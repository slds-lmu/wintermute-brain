"""Send MCP calls to the GPU or CPU qmd. Searches race; other calls need no model."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx
from fastapi.responses import JSONResponse, Response

log = logging.getLogger(__name__)

HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length",
}
# Status for a request whose client has gone; nobody reads the response.
CLIENT_CLOSED = 499


class BackendFailed(Exception):
    """A qmd instance could not answer, as opposed to answering with an error."""


@dataclass
class Call:
    method: str
    body: bytes
    headers: dict[str, str]
    gpu_admitted: bool = False


def _is_search(message: object) -> bool:
    if not isinstance(message, dict) or message.get("method") != "tools/call":
        return False
    params = message.get("params")
    return isinstance(params, dict) and params.get("name") == "query"


def is_search(payload: object) -> bool:
    if isinstance(payload, list):
        return any(_is_search(message) for message in payload)
    return _is_search(payload)


def without_subscriptions(payload: object, body: bytes) -> bytes:
    """Ask for an empty subscription, which qmd acknowledges and closes at once.

    qmd's HTTP server buffers a whole response before sending it, so an open
    subscription would never deliver its acknowledgement or any notification.
    Invalid requests stay unchanged for qmd to reject.
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
        # Index refreshes close GPU admission for a fraction of a second.
        self.cpu_grace = float(os.environ.get("BRAIN_CPU_GRACE", "1"))
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
    def _reply(upstream: httpx.Response, backend: str) -> Response:
        headers = {
            name: value for name, value in upstream.headers.items()
            if name.lower() not in HOP_HEADERS | {"content-encoding"}
        }
        headers["X-Brain-Backend"] = backend
        return Response(upstream.content, status_code=upstream.status_code, headers=headers)

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
                    return self._reply(await self._forward(self.cpu.upstream, call, remaining), "cpu")
                if self.runtime.ready.is_set():
                    async with self.runtime.admission():
                        return self._reply(
                            await self._forward(self.runtime.upstream, call, remaining), "gpu",
                        )
            except BackendFailed as error:
                # The CPU qmd restarts within a second after an aborted search.
                log.info("Retrying a call without model use: %s", error)
            await asyncio.sleep(0.1)

    async def _gpu_attempt(self, call: Call, delay: float = 0) -> httpx.Response:
        if delay:
            await asyncio.sleep(delay)
        async with self.runtime.admission():
            call.gpu_admitted = True
            return await self._forward(self.runtime.upstream, call, self.gpu_search_timeout)

    async def _cpu_attempt(self, call: Call) -> httpx.Response:
        async with self.cpu.search_slot:
            await self.cpu.available.wait()
            try:
                return await self._forward(self.cpu.upstream, call, self.search_wait)
            except asyncio.CancelledError:
                # Disconnecting from qmd does not stop its search.
                self.cpu.abort()
                raise

    async def search(self, call: Call, disconnected: Callable[[], Awaitable[bool]]) -> Response:
        """Run a search on the GPU; while it is taken, race the CPU against it."""
        started = time.monotonic()
        deadline = started + self.search_wait
        start_cpu_at = started + self.cpu_grace
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
                            call.gpu_admitted = False
                            start_cpu_at = 0
                            gpu = asyncio.create_task(self._gpu_attempt(call, delay=1))
                        else:
                            cpu_failures += 1
                            cpu = None
                        continue
                    log.info("Search answered by the %s qmd in %.1f s", backend, time.monotonic() - started)
                    return self._reply(response, backend)
                now = time.monotonic()
                if cpu is None and not call.gpu_admitted and now >= start_cpu_at and cpu_failures < 3:
                    cpu = asyncio.create_task(self._cpu_attempt(call))
                if now >= deadline:
                    return self._unavailable("Search is waiting for a free backend", 30)
                if await disconnected():
                    return Response(status_code=CLIENT_CLOSED)
        finally:
            attempts = [task for task in (gpu, cpu) if task is not None]
            for task in attempts:
                task.cancel()
            await asyncio.gather(*attempts, return_exceptions=True)
