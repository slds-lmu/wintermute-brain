import asyncio
import fcntl
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fakeredis.aioredis
import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brain_server import github_auth
from brain_server.app import RepoAccess, create_app
from brain_server.runtime import QmdRuntime, QueueDemand, live_gpu_requests


class Demand:
    queued = False

    async def busy(self):
        return self.queued


class Process:
    pid = 12345
    returncode = None

    async def wait(self):
        return self.returncode


class Runtime(QmdRuntime):
    def configure(self):
        pass

    async def refresh(self):
        self.last_refresh = time.monotonic()
        self.revision = "revision"

    async def warm(self):
        pass


@pytest.fixture
def runtime_environment(tmp_path, monkeypatch):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    (tmp_path / "repo" / ".git" / "brain-ready").touch()
    monkeypatch.setenv("BRAIN_DIR", str(tmp_path / "repo"))
    monkeypatch.setenv("BRAIN_GPU_LOCK", str(tmp_path / "locks" / "gpu.lock"))
    monkeypatch.setenv("BRAIN_QMD_STATE", str(tmp_path / "state"))


def test_warm_residency_and_queue_batch_handoff(runtime_environment, monkeypatch):
    async def exercise():
        demand = Demand()
        runtime = Runtime(demand)
        processes = []

        async def spawn(*args, **kwargs):
            process = Process()
            processes.append(process)
            return process

        def stop(pid, sig):
            processes[-1].returncode = 0

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        monkeypatch.setattr(os, "killpg", stop)
        try:
            await runtime.step()
            await runtime.step()
            assert runtime.ready.is_set()
            assert len(processes) == 1
            with runtime.lock_path.open("a") as handle:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            demand.queued = True
            await runtime.step()
            assert not runtime.ready.is_set()
            assert runtime.lock is None
            assert processes[0].returncode == 0
            # More queued or executing OCR work must not reload the models.
            await runtime.step()
            await runtime.step()
            assert len(processes) == 1
            demand.queued = False
            await runtime.step()
            assert len(processes) == 1  # quiet period between jobs
            runtime.cooldown_until = 0
            await runtime.step()
            assert runtime.ready.is_set()
            assert len(processes) == 2
        finally:
            await runtime.pause()
            await runtime.client.aclose()

    asyncio.run(exercise())


def test_handoff_drains_an_active_search(runtime_environment):
    async def exercise():
        runtime = Runtime(Demand())
        runtime.ready.set()
        entered = asyncio.Event()
        finish = asyncio.Event()

        async def search():
            async with runtime.admission():
                entered.set()
                await finish.wait()

        active = asyncio.create_task(search())
        await entered.wait()
        handoff = asyncio.create_task(runtime.pause())
        await asyncio.sleep(0)
        assert not handoff.done()
        assert not runtime.ready.is_set()
        finish.set()
        await active
        await handoff
        assert runtime.active == 0
        await runtime.client.aclose()

    asyncio.run(exercise())


def test_pull_during_indexing_is_refreshed_on_the_next_pass(runtime_environment):
    async def exercise():
        runtime = QmdRuntime(Demand())
        head = "old"
        updates = []

        async def command(*args, **kwargs):
            nonlocal head
            if args[0] == "git":
                return head
            if args[:2] == ("qmd", "update"):
                updates.append(head)
            if args[:2] == ("qmd", "embed"):
                head = "new"
            return ""

        runtime.command = command
        await runtime.refresh()
        assert runtime.revision == "old"
        await runtime.refresh()
        assert runtime.revision == "new"
        await runtime.refresh()
        assert updates == ["old", "new"]
        await runtime.client.aclose()

    asyncio.run(exercise())


def test_live_request_and_crashed_request_cleanup(tmp_path):
    path = tmp_path / "job.request"
    with path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        assert live_gpu_requests(tmp_path)
        assert path.exists()
    assert not live_gpu_requests(tmp_path)
    assert not path.exists()


def test_queue_checks_waiting_running_and_dequeued_jobs():
    async def exercise():
        client = fakeredis.aioredis.FakeRedis()
        demand = QueueDemand(client, ["mineru", "whisper"])
        try:
            assert not await demand.busy()
            await client.lpush("rq:queue:mineru", "job")
            assert await demand.busy()
            await client.delete("rq:queue:mineru")
            await client.lpush("rq:queue:mineru:intermediate", "job")
            assert await demand.busy()
            await client.delete("rq:queue:mineru:intermediate")
            await client.zadd("rq:wip:mineru", {"job:execution": time.time() + 60})
            assert await demand.busy()
            await client.zadd("rq:wip:mineru", {"job:execution": time.time() - 60})
            assert not await demand.busy()
            # A Whisper batch also waits on the same GPU lock.
            await client.lpush("rq:queue:whisper", "transcription")
            assert await demand.busy()
        finally:
            await client.aclose()

    asyncio.run(exercise())


def test_app_token_cache_renews_before_expiry(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAIN_AUTH_CACHE", str(tmp_path / "auth"))
    issued = []

    def mint():
        issued.append(True)
        return {
            "token": "installation-token-" + str(len(issued)),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }

    monkeypatch.setattr(github_auth, "mint_token", mint)
    assert github_auth.get_token() == "installation-token-1"
    assert github_auth.get_token() == "installation-token-1"
    cache = tmp_path / "auth" / "installation-token.json"
    assert cache.stat().st_mode & 0o777 == 0o600
    cache.write_text(json.dumps({
        "token": "old", "expires_at": datetime.now(timezone.utc).isoformat(),
    }))
    assert github_auth.get_token() == "installation-token-2"
    assert len(issued) == 2


@pytest.mark.parametrize("permission, expected", [(True, True), (False, False)])
def test_personal_repo_access_and_hashed_cache(permission, expected):
    async def exercise():
        calls = []

        def github(request):
            calls.append(request)
            return httpx.Response(
                200, json={"login": "member"} if request.url.path == "/user"
                else {"permissions": {"pull": permission}},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(github)) as client:
            access = RepoAccess(client, "slds-lmu/wintermute-brain")
            assert await access.allowed("personal-token") is expected
            assert await access.allowed("personal-token") is expected
            assert len(calls) == 2
            assert "personal-token" not in repr(access.cache)

    asyncio.run(exercise())


class GatewayRuntime:
    state = "ready"
    upstream = "http://qmd"
    busy = False

    async def run(self):
        await asyncio.Event().wait()

    def status(self):
        return {"state": self.state, "ready": not self.busy}

    @asynccontextmanager
    async def admission(self):
        if self.busy:
            raise TimeoutError
        yield


class Access:
    async def allowed(self, token):
        return token == "member-token"


def test_gateway_auth_protocol_and_gpu_wait(monkeypatch):
    monkeypatch.setenv("BRAIN_SEARCH_SERVICE_TOKEN", "internal-service-token")
    runtime = GatewayRuntime()
    app = create_app(runtime=runtime, access=Access())
    seen = []

    def qmd(request):
        seen.append(request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}})

    with TestClient(app) as client:
        assert client.post("/mcp", json={}).status_code == 401
        assert client.post("/mcp", headers={"Authorization": "Bearer invalid"}).status_code == 401
        app.state.qmd = httpx.AsyncClient(transport=httpx.MockTransport(qmd))
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = client.post("/mcp", json=payload, headers={
            "Authorization": "Bearer member-token",
            "Origin": "https://public.example",
            "MCP-Protocol-Version": "2026-07-28",
        })
        assert response.status_code == 200
        assert json.loads(seen[0].content) == payload
        assert seen[0].headers["MCP-Protocol-Version"] == "2026-07-28"
        assert "authorization" not in seen[0].headers
        assert "origin" not in seen[0].headers
        assert client.post("/mcp", json=payload, headers={
            "Authorization": "Bearer internal-service-token",
        }).status_code == 401
        assert client.post("/internal/mcp", json=payload, headers={
            "Authorization": "Bearer member-token",
        }).status_code == 401
        assert client.post("/internal/mcp", json=payload, headers={
            "Authorization": "Bearer internal-service-token",
        }).status_code == 200
        runtime.busy = True
        response = client.post("/mcp", json=payload, headers={"Authorization": "Bearer member-token"})
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "5"
        assert client.get("/healthz").status_code == 200
