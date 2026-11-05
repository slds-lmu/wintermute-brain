import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brain_server.access import ChecksThrottled, GitHubUnavailable
from brain_server.app import create_app
from brain_server.routing import Call, Router, is_search, without_subscriptions

SEARCH = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "query", "arguments": {"query": "x"}}}
ANSWER = {"jsonrpc": "2.0", "id": 1, "result": {}}
MEMBER = {"Authorization": "Bearer member-token"}


class Gpu:
    upstream = "http://gpu"
    state = "paused"

    def __init__(self, ready=False):
        self.ready = asyncio.Event()
        if ready:
            self.ready.set()
        self.active = 0
        self.admissions = 0

    async def run(self):
        await asyncio.Event().wait()

    def status(self):
        return {"state": self.state, "ready": self.ready.is_set(), "revision": "secret-revision"}

    @asynccontextmanager
    async def admission(self):
        await self.ready.wait()
        self.active += 1
        self.admissions += 1
        try:
            yield
        finally:
            self.active -= 1


class Cpu:
    upstream = "http://cpu"

    def __init__(self, available=True):
        self.available = asyncio.Event()
        if available:
            self.available.set()
        self.search_slot = asyncio.Semaphore(1)
        self.aborts = 0

    async def run(self):
        await asyncio.Event().wait()

    def abort(self):
        self.aborts += 1


class Upstreams:
    """Both qmd instances: answer at once unless told to block or fail."""

    def __init__(self):
        self.calls = []
        self.block = {"gpu": None, "cpu": None}
        self.fail = {"gpu": 0, "cpu": 0}
        self.started = {"gpu": asyncio.Event(), "cpu": asyncio.Event()}

    async def __call__(self, request):
        host = request.url.host
        self.calls.append(host)
        self.started[host].set()
        if self.block[host] is not None:
            await self.block[host].wait()
        if self.fail[host]:
            self.fail[host] -= 1
            raise httpx.ConnectError("qmd is gone")
        return httpx.Response(200, json=ANSWER)


async def never_disconnected():
    return False


def call():
    return Call("POST", json.dumps(SEARCH).encode(), {})


@asynccontextmanager
async def routed(ready=False, available=True, **settings):
    upstreams = Upstreams()
    gpu, cpu = Gpu(ready), Cpu(available)
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstreams)) as client:
        router = Router(gpu, cpu, client)
        router.cpu_grace = 0
        router.tick = 0.01
        for name, value in settings.items():
            setattr(router, name, value)
        yield router, gpu, cpu, upstreams


def run(coroutine):
    asyncio.run(asyncio.wait_for(coroutine, 5))


def test_search_uses_only_the_gpu_while_it_is_available():
    async def exercise():
        async with routed(ready=True, cpu_grace=0.05) as (router, gpu, cpu, upstreams):
            response = await router.search(call(), never_disconnected)
            assert response.status_code == 200
            assert response.headers["x-brain-backend"] == "gpu"
            assert upstreams.calls == ["gpu"]
            assert gpu.active == 0

    run(exercise())


def test_cpu_stays_out_of_a_slow_gpu_search():
    async def exercise():
        async with routed(ready=True) as (router, gpu, cpu, upstreams):
            upstreams.block["gpu"] = asyncio.Event()
            search = asyncio.create_task(router.search(call(), never_disconnected))
            await asyncio.sleep(0.05)
            upstreams.block["gpu"].set()
            assert (await search).headers["x-brain-backend"] == "gpu"
            assert upstreams.calls == ["gpu"]

    run(exercise())


def test_search_runs_on_the_cpu_while_the_gpu_is_taken():
    async def exercise():
        async with routed() as (router, gpu, cpu, upstreams):
            response = await router.search(call(), never_disconnected)
            assert response.headers["x-brain-backend"] == "cpu"
            assert upstreams.calls == ["cpu"]
            assert cpu.aborts == 0
            assert gpu.admissions == 0

    run(exercise())


def test_brief_gpu_unavailability_does_not_start_the_cpu():
    async def exercise():
        async with routed(cpu_grace=0.2) as (router, gpu, cpu, upstreams):
            search = asyncio.create_task(router.search(call(), never_disconnected))
            await asyncio.sleep(0.02)
            gpu.ready.set()
            assert (await search).headers["x-brain-backend"] == "gpu"
            assert upstreams.calls == ["gpu"]

    run(exercise())


def test_gpu_winning_the_race_kills_the_cpu_search():
    async def exercise():
        async with routed() as (router, gpu, cpu, upstreams):
            upstreams.block["cpu"] = asyncio.Event()
            search = asyncio.create_task(router.search(call(), never_disconnected))
            await upstreams.started["cpu"].wait()
            assert cpu.aborts == 0
            gpu.ready.set()
            response = await search
            assert response.headers["x-brain-backend"] == "gpu"
            assert cpu.aborts == 1
            assert not cpu.search_slot.locked()

    run(exercise())


def test_cpu_winning_the_race_releases_gpu_admission_and_keeps_the_cpu_qmd():
    async def exercise():
        async with routed() as (router, gpu, cpu, upstreams):
            upstreams.block["cpu"] = asyncio.Event()
            upstreams.block["gpu"] = asyncio.Event()
            search = asyncio.create_task(router.search(call(), never_disconnected))
            await upstreams.started["cpu"].wait()
            gpu.ready.set()
            await upstreams.started["gpu"].wait()
            assert gpu.active == 1
            upstreams.block["cpu"].set()
            response = await search
            assert response.headers["x-brain-backend"] == "cpu"
            assert gpu.active == 0
            assert cpu.aborts == 0

    run(exercise())


def test_cpu_runs_one_search_at_a_time_and_queued_searches_cost_no_kill():
    async def exercise():
        async with routed() as (router, gpu, cpu, upstreams):
            upstreams.block["cpu"] = asyncio.Event()
            first = asyncio.create_task(router.search(call(), never_disconnected))
            await upstreams.started["cpu"].wait()
            second = asyncio.create_task(router.search(call(), never_disconnected))
            await asyncio.sleep(0.05)
            assert upstreams.calls == ["cpu"]
            gone = {"value": False}

            async def disconnected():
                return gone["value"]

            third = asyncio.create_task(router.search(call(), disconnected))
            await asyncio.sleep(0.03)
            gone["value"] = True
            assert (await third).status_code == 499
            assert cpu.aborts == 0
            upstreams.block["cpu"].set()
            assert (await first).status_code == 200
            assert (await second).status_code == 200
            assert upstreams.calls == ["cpu", "cpu"]

    run(exercise())


def test_search_interrupted_on_the_gpu_fails_over_to_the_cpu():
    async def exercise():
        async with routed(ready=True, cpu_grace=60) as (router, gpu, cpu, upstreams):
            upstreams.fail["gpu"] = 1
            gpu.ready.clear()
            gpu.ready.set()
            response = await router.search(call(), never_disconnected)
            assert response.status_code == 200
            assert response.headers["x-brain-backend"] == "cpu"
            assert gpu.active == 0

    run(exercise())


def test_failed_cpu_search_is_retried_then_left_to_the_gpu():
    async def exercise():
        async with routed() as (router, gpu, cpu, upstreams):
            upstreams.fail["cpu"] = 100
            search = asyncio.create_task(router.search(call(), never_disconnected))
            await asyncio.sleep(0.2)
            assert upstreams.calls == ["cpu"] * 3
            gpu.ready.set()
            assert (await search).headers["x-brain-backend"] == "gpu"

    run(exercise())


def test_gpu_error_response_is_an_answer_but_server_failure_is_not():
    async def exercise():
        answers = {"gpu": httpx.Response(500), "cpu": httpx.Response(400, json={"error": "invalid"})}

        async def handler(request):
            return answers[request.url.host]

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            router = Router(Gpu(ready=True), Cpu(), client)
            router.tick = 0.01
            response = await router.search(call(), never_disconnected)
            assert response.status_code == 400
            assert response.headers["x-brain-backend"] == "cpu"

    run(exercise())


def test_disconnect_kills_the_running_search_and_frees_the_slot():
    async def exercise():
        async with routed() as (router, gpu, cpu, upstreams):
            upstreams.block["cpu"] = asyncio.Event()
            gone = asyncio.Event()

            async def disconnected():
                return gone.is_set()

            search = asyncio.create_task(router.search(call(), disconnected))
            await upstreams.started["cpu"].wait()
            gone.set()
            assert (await search).status_code == 499
            assert cpu.aborts == 1
            assert not cpu.search_slot.locked()

    run(exercise())


def test_search_gives_up_at_the_deadline():
    async def exercise():
        async with routed(available=False, search_wait=0.05) as (router, gpu, cpu, upstreams):
            response = await router.search(call(), never_disconnected)
            assert response.status_code == 503
            assert response.headers["retry-after"] == "30"
            assert upstreams.calls == []
            assert not cpu.search_slot.locked()

    run(exercise())


def test_calls_without_model_use_ignore_the_gpu():
    async def exercise():
        async with routed() as (router, gpu, cpu, upstreams):
            response = await router.control(Call("POST", b"{}", {}))
            assert response.headers["x-brain-backend"] == "cpu"
            assert gpu.admissions == 0

    run(exercise())


def test_calls_without_model_use_run_during_a_cpu_search():
    async def exercise():
        async with routed() as (router, gpu, cpu, upstreams):
            await cpu.search_slot.acquire()
            response = await router.control(Call("POST", b"{}", {}))
            assert response.headers["x-brain-backend"] == "cpu"

    run(exercise())


def test_calls_without_model_use_retry_across_a_cpu_restart():
    async def exercise():
        async with routed() as (router, gpu, cpu, upstreams):
            upstreams.fail["cpu"] = 1
            response = await router.control(Call("POST", b"{}", {}))
            assert response.status_code == 200
            assert upstreams.calls == ["cpu", "cpu"]

    run(exercise())


def test_calls_without_model_use_fall_back_to_the_gpu_then_give_up():
    async def exercise():
        async with routed(ready=True, available=False, control_wait=0.2) as (router, gpu, cpu, upstreams):
            response = await router.control(Call("POST", b"{}", {}))
            assert response.headers["x-brain-backend"] == "gpu"
            assert gpu.active == 0
            gpu.ready.clear()
            router.control_wait = 0.05
            response = await router.control(Call("POST", b"{}", {}))
            assert response.status_code == 503

    run(exercise())


@pytest.mark.parametrize("payload, expected", [
    (SEARCH, True),
    ([{"method": "tools/list"}, SEARCH], True),
    ({"method": "tools/call", "params": {"name": "get"}}, False),
    ({"method": "tools/call", "params": {"name": "status"}}, False),
    ({"method": "tools/call", "params": "query"}, False),
    ({"method": "tools/list"}, False),
    ([], False),
    (None, False),
    ("query", False),
])
def test_search_classification(payload, expected):
    assert is_search(payload) is expected


def test_listen_filter_is_emptied_and_other_requests_stay_untouched():
    listen = {
        "jsonrpc": "2.0", "id": 7, "method": "subscriptions/listen",
        "params": {"notifications": {"toolsListChanged": True}, "_meta": {"a": 1}},
    }
    rewritten = json.loads(without_subscriptions(listen, b"original"))
    assert rewritten["params"] == {"notifications": {}, "_meta": {"a": 1}}
    assert rewritten["id"] == 7
    invalid = {"method": "subscriptions/listen", "params": {}}
    assert without_subscriptions(invalid, b"original") == b"original"
    assert without_subscriptions({"method": "tools/list"}, b"original") == b"original"
    assert without_subscriptions(None, b"original") == b"original"


class Access:
    failure = None

    async def allowed(self, token, client_address=""):
        self.client_address = client_address
        if self.failure is not None:
            raise self.failure
        return token == "member-token"


@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setenv("BRAIN_SEARCH_SERVICE_TOKEN", "internal-service-token")
    seen = []

    def qmd(request):
        seen.append(request)
        return httpx.Response(200, json=ANSWER)

    gpu, cpu, access = Gpu(ready=True), Cpu(), Access()
    client = httpx.AsyncClient(transport=httpx.MockTransport(qmd))
    app = create_app(runtime=gpu, cpu=cpu, access=access, qmd_client=client)
    with TestClient(app) as test_client:
        yield test_client, seen, gpu, cpu, access


def test_gateway_authentication(gateway):
    client, seen, gpu, cpu, access = gateway
    assert client.post("/mcp", json={}).status_code == 401
    assert client.post("/mcp", json={}, headers={"Authorization": "Basic x"}).status_code == 401
    assert client.post("/mcp", json={}, headers={"Authorization": "Bearer invalid"}).status_code == 401
    service = {"Authorization": "Bearer internal-service-token"}
    assert client.post("/mcp", json={}, headers=service).status_code == 401
    assert client.post("/internal/mcp", json={}, headers=MEMBER).status_code == 401
    assert client.post("/internal/mcp", json={}, headers=service).status_code == 200
    assert client.post("/mcp", json={}, headers=MEMBER).status_code == 200
    assert len(seen) == 2


@pytest.mark.parametrize("failure, status", [
    (GitHubUnavailable("down"), 503),
    (ChecksThrottled(), 429),
])
def test_gateway_reports_authorization_trouble_as_such(gateway, failure, status):
    client, seen, gpu, cpu, access = gateway
    access.failure = failure
    response = client.post("/mcp", json={}, headers=MEMBER)
    assert response.status_code == status
    assert response.headers["Retry-After"]
    assert "WWW-Authenticate" not in response.headers
    assert not seen


def test_gateway_limits_clients_by_the_address_caddy_saw(gateway):
    client, seen, gpu, cpu, access = gateway
    client.post("/mcp", json={}, headers={**MEMBER, "X-Forwarded-For": "203.0.113.9, 198.51.100.7"})
    assert access.client_address == "198.51.100.7"


def test_gateway_forwards_protocol_headers_but_no_credentials(gateway):
    client, seen, gpu, cpu, access = gateway
    response = client.post("/mcp", json={"method": "tools/list"}, headers={
        **MEMBER, "Origin": "https://public.example", "MCP-Protocol-Version": "2026-07-28",
    })
    assert response.status_code == 200
    assert seen[0].url.host == "cpu"
    assert seen[0].headers["MCP-Protocol-Version"] == "2026-07-28"
    assert "authorization" not in seen[0].headers
    assert "origin" not in seen[0].headers


def test_gateway_sends_searches_to_the_gpu_and_listeners_to_the_cpu_with_no_filter(gateway):
    client, seen, gpu, cpu, access = gateway
    assert client.post("/mcp", json=SEARCH, headers=MEMBER).headers["X-Brain-Backend"] == "gpu"
    assert gpu.admissions == 1
    response = client.post("/mcp", headers=MEMBER, json={
        "jsonrpc": "2.0", "id": 2, "method": "subscriptions/listen",
        "params": {"notifications": {"toolsListChanged": True}},
    })
    assert response.headers["X-Brain-Backend"] == "cpu"
    assert json.loads(seen[-1].content)["params"]["notifications"] == {}
    assert gpu.admissions == 1


def test_gateway_rejects_large_bodies_and_passes_malformed_ones_to_qmd(gateway):
    client, seen, gpu, cpu, access = gateway
    response = client.post("/mcp", content=b"x" * (1024 * 1024 + 1), headers=MEMBER)
    assert response.status_code == 413
    assert not seen
    assert client.post("/mcp", content=b"not json", headers=MEMBER).status_code == 200
    assert seen[0].content == b"not json"


@pytest.mark.parametrize("state, ready, status", [
    ("ready", True, 200),
    ("paused", False, 200),
    ("indexing", False, 200),
    ("error", False, 503),
    ("starting", False, 503),
])
def test_health_reports_state_and_no_content_revision(gateway, state, ready, status):
    client, seen, gpu, cpu, access = gateway
    gpu.state = state
    if not ready:
        gpu.ready.clear()
    response = client.get("/healthz")
    assert response.status_code == status
    assert response.json()["state"] == state
    assert response.json()["ready"] is ready
    assert response.json()["cpu"] is True
    assert "revision" not in response.json()
