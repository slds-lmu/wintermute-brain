"""Forward MCP calls to qmd, with a limit on the searches that use GPU memory."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass

import httpx
from fastapi.responses import JSONResponse, Response

log = logging.getLogger(__name__)

HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length",
}


@dataclass
class Call:
    method: str
    body: bytes
    headers: dict[str, str]
    discovery: bool = False


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


def without_list_changed(content: bytes) -> bytes:
    """Stop advertising change notifications, so that clients do not subscribe.

    qmd's HTTP server buffers a whole response before sending it, so it can
    deliver no notification. Claude Code would otherwise wait 25 seconds for an
    acknowledgement that never arrives, and reopen a closed stream three times.
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
    def __init__(self, runtime, client: httpx.AsyncClient) -> None:
        self.runtime = runtime
        self.client = client
        # Claude Code abandons a request after 60 s without response headers.
        self.search_wait = float(os.environ.get("BRAIN_SEARCH_WAIT", "55"))
        self.control_wait = float(os.environ.get("BRAIN_CONTROL_WAIT", "30"))
        # Each running search allocates GPU memory: 3.4 GB idle, 5.1 GB with four.
        self.search_slots = asyncio.Semaphore(int(os.environ.get("BRAIN_SEARCH_SLOTS", "2")))
        self.search_limit = int(os.environ.get("BRAIN_SEARCH_LIMIT", "10"))
        self.searches = 0

    async def _forward(self, call: Call, deadline: float) -> httpx.Response:
        """Forward once qmd is up; a call that needs no change is safe to repeat."""
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            await asyncio.wait_for(self.runtime.ready.wait(), remaining)
            try:
                # httpx's own timeout applies per read, not to the whole request.
                response = await asyncio.wait_for(
                    self.client.request(
                        call.method, self.runtime.upstream + "/mcp", content=call.body, headers=call.headers,
                        timeout=None,
                    ),
                    max(0.001, deadline - time.monotonic()),
                )
            except httpx.HTTPError as error:
                # qmd was restarted or crashed.
                log.info("Retrying a call: %s", type(error).__name__)
            else:
                if response.status_code < 500:
                    return response
                log.warning("qmd answered %s; retrying", response.status_code)
            await asyncio.sleep(0.25)

    def _unavailable(self, detail: str, retry_after: int = 5) -> JSONResponse:
        return JSONResponse(
            {"detail": detail, "state": self.runtime.state},
            status_code=503, headers={"Retry-After": str(retry_after)},
        )

    @staticmethod
    def _reply(upstream: httpx.Response, discovery: bool = False) -> Response:
        headers = {
            name: value for name, value in upstream.headers.items()
            if name.lower() not in HOP_HEADERS | {"content-encoding"}
        }
        content = without_list_changed(upstream.content) if discovery else upstream.content
        return Response(content, status_code=upstream.status_code, headers=headers)

    async def control(self, call: Call) -> Response:
        """Run a call that loads no model."""
        if self.runtime.failing and not self.runtime.ready.is_set():
            return self._unavailable("Search backend unavailable")
        try:
            response = await self._forward(call, time.monotonic() + self.control_wait)
        except (TimeoutError, asyncio.TimeoutError):
            return self._unavailable("Search backend unavailable")
        return self._reply(response, call.discovery)

    async def search(self, call: Call) -> Response:
        """Run a search once a slot is free, within the time clients wait."""
        if self.runtime.failing and not self.runtime.ready.is_set():
            # Answer at once, so that clients use their local fallback.
            return self._unavailable("Search backend unavailable", 30)
        if self.searches >= self.search_limit:
            log.warning("Too many searches at once")
            return self._unavailable("Search is busy", 30)
        self.searches += 1
        started = time.monotonic()
        deadline = started + self.search_wait
        try:
            await asyncio.wait_for(self.search_slots.acquire(), self.search_wait)
            try:
                broken = self.runtime.broken_searches
                response = await self._forward(call, deadline)
                # Let the log line of a failed search arrive before judging it.
                await asyncio.sleep(0.05)
                if self.runtime.broken_searches != broken:
                    # qmd answered "no results" because it could not search.
                    return self._unavailable("Search lacks GPU memory", 30)
                log.info("Search took %.1f s", time.monotonic() - started)
                return self._reply(response)
            finally:
                self.search_slots.release()
        except (TimeoutError, asyncio.TimeoutError):
            log.warning("Search gave up after %.0f s", time.monotonic() - started)
            return self._unavailable("Search is taking too long", 30)
        finally:
            self.searches -= 1
