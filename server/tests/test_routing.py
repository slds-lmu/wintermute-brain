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
from brain_server.routing import (
    Call,
    Router,
    as_event,
    is_discovery,
    is_search,
    without_list_changed,
    without_subscriptions,
)

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


async def body_of(response):
    return b"".join([chunk async for chunk in response.body_iterator])


def test_quick_search_answers_plainly_even_if_events_are_accepted():
    async def exercise():
        async with routed(ready=True) as (router, gpu, cpu, upstreams):
            answer = call()
            answer.event_id = 1
            response = await router.search(answer, never_disconnected)
            assert response.headers["content-type"] == "application/json"
            assert json.loads(response.body) == ANSWER

    run(exercise())


def test_slow_search_commits_to_events_with_keepalives_and_then_the_answer():
    async def exercise():
        async with routed(answer_wait=0.01, keepalive=0.01) as (router, gpu, cpu, upstreams):
            upstreams.block["cpu"] = asyncio.Event()
            slow = call()
            slow.event_id = 7
            response = await router.search(slow, never_disconnected)
            assert response.media_type == "text/event-stream"
            assert "no-transform" in response.headers["cache-control"]
            chunks = response.body_iterator
            assert await chunks.__anext__() == b": searching\n\n"
            assert await chunks.__anext__() == b": searching\n\n"
            upstreams.block["cpu"].set()
            rest = b"".join([chunk async for chunk in chunks])
            event = rest.split(b"event: message\ndata: ")[1]
            assert rest.endswith(b"\n\n")
            assert json.loads(event) == ANSWER

    run(exercise())


def test_slow_search_without_event_support_keeps_waiting_for_a_plain_answer():
    async def exercise():
        async with routed(answer_wait=0.01) as (router, gpu, cpu, upstreams):
            upstreams.block["cpu"] = asyncio.Event()
            search = asyncio.create_task(router.search(call(), never_disconnected))
            await asyncio.sleep(0.05)
            assert not search.done()
            upstreams.block["cpu"].set()
            assert (await search).headers["content-type"] == "application/json"

    run(exercise())


def test_deadline_after_committing_to_events_is_a_json_rpc_error():
    async def exercise():
        async with routed(available=False, answer_wait=0.01, search_wait=0.05, keepalive=0.01) as (router, gpu, cpu, upstreams):
            slow = call()
            slow.event_id = 7
            response = await router.search(slow, never_disconnected)
            event = (await body_of(response)).split(b"event: message\ndata: ")[1]
            message = json.loads(event)
            assert message["id"] == 7
            assert message["error"]["message"] == "Search is waiting for a free backend"

    run(exercise())


def test_disconnect_from_the_event_stream_kills_the_search():
    async def exercise():
        async with routed(answer_wait=0.01, keepalive=0.01) as (router, gpu, cpu, upstreams):
            upstreams.block["cpu"] = asyncio.Event()
            slow = call()
            slow.event_id = 7
            response = await router.search(slow, never_disconnected)
            chunks = response.body_iterator
            await chunks.__anext__()
            await upstreams.started["cpu"].wait()
            await chunks.aclose()
            await asyncio.sleep(0.05)
            assert cpu.aborts == 1
            assert not cpu.search_slot.locked()

    run(exercise())


def test_events_pass_along_error_answers_and_other_bodies():
    from fastapi.responses import Response

    rpc_error = {"jsonrpc": "2.0", "id": 3, "error": {"code": -32602, "message": "invalid"}}
    plain = as_event(Response(json.dumps(rpc_error), media_type="application/json"), 3)
    assert json.loads(plain.split(b"data: ")[1]) == rpc_error
    assert b"Search failed" in as_event(Response(b"not json"), 3)
    stream = b"event: message\ndata: {}\n\n"
    assert as_event(Response(stream, media_type="text/event-stream"), 3) == stream


def test_gateway_offers_events_only_for_a_single_request_accepting_them(gateway):
    client, seen, gpu, cpu, access = gateway
    router = client.app.state.router
    calls = []
    original = router.search

    async def spy(call, disconnected):
        calls.append(call.event_id)
        return await original(call, disconnected)

    router.search = spy
    both = {**MEMBER, "Accept": "application/json, text/event-stream"}
    assert client.post("/mcp", json=SEARCH, headers=both).status_code == 200
    assert client.post("/mcp", json=SEARCH, headers={**MEMBER, "Accept": "application/json"}).status_code == 200
    assert client.post("/mcp", json=[SEARCH], headers=both).status_code == 200
    assert calls == [1, None, None]


def test_discovery_stops_advertising_change_notifications():
    assert is_discovery({"method": "server/discover"})
    assert is_discovery({"method": "initialize"})
    assert not is_discovery({"method": "tools/list"})
    assert not is_discovery([{"method": "initialize"}])
    answer = {"jsonrpc": "2.0", "id": 1, "result": {
        "capabilities": {"tools": {"listChanged": True}, "resources": {"listChanged": True, "subscribe": True}, "logging": {}},
        "instructions": "keep",
    }}
    assert json.loads(without_list_changed(json.dumps(answer).encode())) == {"jsonrpc": "2.0", "id": 1, "result": {
        "capabilities": {"tools": {}, "resources": {"subscribe": True}, "logging": {}},
        "instructions": "keep",
    }}
    for other in (b"event: message\ndata: {}\n\n", b"[]", b'{"result": {}}', b'{"result": {"capabilities": 1}}', b'{"result": 1}'):
        assert without_list_changed(other) == other


def test_gateway_rewrites_discovery_answers_only(monkeypatch):
    monkeypatch.setenv("BRAIN_SEARCH_SERVICE_TOKEN", "internal-service-token")
    answer = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {"tools": {"listChanged": True}}}}

    def qmd(request):
        return httpx.Response(200, json=answer)

    client = httpx.AsyncClient(transport=httpx.MockTransport(qmd))
    app = create_app(runtime=Gpu(), cpu=Cpu(), access=Access(), qmd_client=client)
    with TestClient(app) as test_client:
        found = test_client.post("/mcp", json={"method": "server/discover"}, headers=MEMBER)
        assert found.json()["result"]["capabilities"] == {"tools": {}}
        other = test_client.post("/mcp", json={"method": "tools/list"}, headers=MEMBER)
        assert other.json() == answer


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
