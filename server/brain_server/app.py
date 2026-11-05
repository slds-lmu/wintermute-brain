"""Authenticated MCP gateway in front of the GPU and CPU qmd."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from .access import ChecksThrottled, GitHubUnavailable, RepoAccess
from .routing import (
    HOP_HEADERS,
    Call,
    Router,
    is_discovery,
    is_search,
    without_subscriptions,
)
from .runtime import CpuQmd, QmdRuntime

MAX_BODY = 1024 * 1024


def client_address(request: Request) -> str:
    # Only Caddy reaches this port, and it appends the address it saw last.
    forwarded = request.headers.get("x-forwarded-for", "").rsplit(",", 1)[-1].strip()
    return forwarded or (request.client.host if request.client else "")


async def authorization_failure(request: Request, access) -> Response | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    allowed = False
    if scheme.lower() == "bearer" and token:
        if request.url.path == "/internal/mcp":
            service_token = os.environ.get("BRAIN_SEARCH_SERVICE_TOKEN", "")
            allowed = bool(service_token) and secrets.compare_digest(token.encode(), service_token.encode())
        else:
            try:
                allowed = await access.allowed(token, client_address(request))
            except GitHubUnavailable as error:
                logging.getLogger(__name__).warning("GitHub cannot authorize a request: %s", error)
                return JSONResponse(
                    {"detail": "GitHub cannot confirm repository access at the moment"},
                    status_code=503, headers={"Retry-After": "30"},
                )
            except ChecksThrottled:
                return JSONResponse(
                    {"detail": "Too many new tokens from this address"},
                    status_code=429, headers={"Retry-After": "60"},
                )
    if allowed:
        return None
    return JSONResponse(
        {"detail": "A GitHub user token with read access to the brain repository is required"},
        status_code=401, headers={"WWW-Authenticate": "Bearer"},
    )


def create_app(runtime=None, cpu=None, access=None, qmd_client=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        logging.basicConfig(
            level=os.environ.get("BRAIN_LOG_LEVEL", "INFO"),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        # At INFO it logs a line per upstream request.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        gpu_qmd = runtime or QmdRuntime()
        cpu_qmd = cpu or CpuQmd(gpu_qmd)
        app.state.runtime = gpu_qmd
        app.state.cpu = cpu_qmd
        async with (
            httpx.AsyncClient(timeout=15) as github,
            httpx.AsyncClient(timeout=180) as own_qmd_client,
        ):
            app.state.access = access or RepoAccess(
                github, os.environ.get("BRAIN_REPO", "slds-lmu/wintermute-brain-content-slds"),
            )
            app.state.router = Router(gpu_qmd, cpu_qmd, qmd_client or own_qmd_client)
            tasks = [asyncio.create_task(gpu_qmd.run()), asyncio.create_task(cpu_qmd.run())]
            try:
                yield
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    async def health():
        # Public: no content revision here. A failing GPU qmd stays visible to
        # monitoring although the CPU qmd keeps answering.
        status = app.state.runtime.status()
        failed = status["state"] in {"starting", "waiting_for_repository", "error", "stopped"}
        return JSONResponse(
            {
                "status": "unavailable" if failed else "ok",
                "state": status["state"],
                "ready": status["ready"],
                "cpu": app.state.cpu.available.is_set(),
            },
            status_code=503 if failed else 200,
        )

    @app.api_route("/internal/mcp", methods=["GET", "POST", "DELETE"])
    @app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
    async def mcp(request: Request):
        failure = await authorization_failure(request, app.state.access)
        if failure is not None:
            return failure
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                return JSONResponse({"detail": "Request exceeds 1 MiB"}, status_code=413)
        try:
            payload = json.loads(body) if body else None
        except (ValueError, RecursionError):
            payload = None
        call = Call(
            method=request.method,
            body=without_subscriptions(payload, bytes(body)),
            headers={
                name: value for name, value in request.headers.items()
                if name.lower() not in HOP_HEADERS | {"authorization", "origin", "accept-encoding"}
            },
            discovery=is_discovery(payload),
        )
        if isinstance(payload, dict) and "text/event-stream" in request.headers.get("accept", ""):
            call.event_id = payload.get("id")
        if is_search(payload):
            return await app.state.router.search(call, request.is_disconnected)
        return await app.state.router.control(call)

    return app


app = create_app()
