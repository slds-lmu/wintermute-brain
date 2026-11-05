"""Authenticated MCP gateway and qmd GPU lifecycle."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .runtime import QmdRuntime

log = logging.getLogger(__name__)
HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length",
}


class McpResponse(StreamingResponse):
    def __init__(self, upstream, admission=None):
        self.upstream = upstream
        self.admission = admission
        super().__init__(
            self.chunks(), status_code=upstream.status_code,
            headers={
                k: v for k, v in upstream.headers.items()
                if k.lower() not in HOP_HEADERS | {"content-encoding"}
            },
        )

    async def chunks(self):
        try:
            async for chunk in self.upstream.aiter_bytes():
                yield chunk
        except httpx.HTTPError:
            if self.admission is not None:
                raise
            log.debug("qmd notification stream closed")

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                await self.upstream.aclose()
            finally:
                if self.admission is not None:
                    await self.admission.__aexit__(None, None, None)


class RepoAccess:
    def __init__(self, client: httpx.AsyncClient, repo: str) -> None:
        self.client = client
        self.repo = repo
        self.cache: dict[str, tuple[float, bool]] = {}

    async def allowed(self, token: str) -> bool:
        digest = hashlib.sha256(token.encode()).hexdigest()
        hit = self.cache.get(digest)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "User-Agent": "wintermute-brain-search",
        }
        try:
            user = await self.client.get("https://api.github.com/user", headers=headers)
            repo = await self.client.get(
                "https://api.github.com/repos/" + self.repo, headers=headers,
            ) if user.status_code == 200 else None
            allowed = bool(
                repo is not None and repo.status_code == 200
                and repo.json().get("permissions", {}).get("pull")
            )
        except (httpx.HTTPError, ValueError):
            # Do not cache transient GitHub failures as permission decisions.
            return False
        if len(self.cache) >= 1024:
            self.cache = {k: v for k, v in self.cache.items() if v[0] > time.monotonic()}
            if len(self.cache) >= 1024:
                self.cache.pop(next(iter(self.cache)))
        self.cache[digest] = (time.monotonic() + (300 if allowed else 30), allowed)
        return allowed


def create_app(runtime=None, access=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.runtime = runtime or QmdRuntime()
        async with (
            httpx.AsyncClient(timeout=15) as github,
            httpx.AsyncClient(timeout=180) as qmd,
        ):
            app.state.access = access or RepoAccess(
                github, os.environ.get("BRAIN_REPO", "slds-lmu/wintermute-brain-content-slds"),
            )
            app.state.qmd = qmd
            task = asyncio.create_task(app.state.runtime.run())
            try:
                yield
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    async def health():
        status = app.state.runtime.status()
        failed = status["state"] in {"starting", "waiting_for_repository", "error", "stopped"}
        return JSONResponse(
            {"status": "unavailable" if failed else "ok", **status},
            status_code=503 if failed else 200,
        )

    @app.api_route("/internal/mcp", methods=["GET", "POST", "DELETE"])
    @app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
    async def mcp(request: Request):
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        service_token = os.environ.get("BRAIN_SEARCH_SERVICE_TOKEN", "")
        if scheme.lower() != "bearer" or not token:
            allowed = False
        elif request.url.path == "/internal/mcp":
            allowed = bool(service_token and secrets.compare_digest(token.encode(), service_token.encode()))
        else:
            allowed = bool(token and await app.state.access.allowed(token))
        if scheme.lower() != "bearer" or not token or not allowed:
            return JSONResponse(
                {"detail": "A GitHub user token with read access to the brain repository is required"},
                status_code=401, headers={"WWW-Authenticate": "Bearer"},
            )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 1024 * 1024:
                return JSONResponse({"detail": "Request exceeds 1 MiB"}, status_code=413)
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in HOP_HEADERS | {"authorization", "origin", "accept-encoding"}
        }
        try:
            payload = json.loads(body) if body else {}
        except ValueError:
            payload = {}
        # Subscription streams stay open between searches. They must not
        # prevent indexing or GPU handoff while the client remains connected.
        listener = request.method == "GET" or (
            isinstance(payload, dict) and payload.get("method") == "subscriptions/listen"
        )
        admission = app.state.runtime.admission()
        entered = False
        try:
            await admission.__aenter__()
            entered = True
            upstream_request = app.state.qmd.build_request(
                request.method, app.state.runtime.upstream + "/mcp",
                content=bytes(body), headers=headers,
            )
            response = await app.state.qmd.send(upstream_request, stream=True)
            if listener:
                await admission.__aexit__(None, None, None)
                entered = False
            result = McpResponse(response, admission if entered else None)
            entered = False
            return result
        except asyncio.TimeoutError:
            return JSONResponse(
                {"detail": "Search is waiting for the GPU", "state": app.state.runtime.state},
                status_code=503, headers={"Retry-After": "5"},
            )
        except httpx.HTTPError:
            log.warning("qmd request failed")
            return JSONResponse({"detail": "Search backend unavailable"}, status_code=502)
        finally:
            if entered:
                await admission.__aexit__(None, None, None)

    return app


app = create_app()
