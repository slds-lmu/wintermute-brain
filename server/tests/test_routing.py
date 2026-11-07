import asyncio
import json
import sys
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
    is_discovery,
    is_search,
    without_list_changed,
    without_subscriptions,
)

SEARCH = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "query", "arguments": {"query": "x"}}}
ANSWER = {"jsonrpc": "2.0", "id": 1, "result": {}}
MEMBER = {"Authorization": "Bearer member-token"}


class Qmd:
    upstream = "http://qmd"
    state = "ready"
    failing = False
    broken_searches = 0
    restart_needed = False

    def __init__(self, ready=True):
        self.ready = asyncio.Event()
        if ready:
            self.ready.set()

    async def run(self):
        await asyncio.Event().wait()

    def status(self):
        return {"state": self.state, "ready": self.ready.is_set(), "failing": self.failing}


class Upstream:
    """Answers at once unless told to block, fail, or report broken searches."""

    def __init__(self, qmd):
        self.qmd = qmd
        self.calls = 0
        self.block = None
        self.fail = 0
        self.refuse = 0
        self.status = 200
        self.running = 0
        self.most_running = 0
        self.break_search = False

    async def __call__(self, request):
        self.calls += 1
        self.running += 1
        self.most_running = max(self.most_running, self.running)
        try:
            if self.block is not None:
                await self.block.wait()
            else:
                await asyncio.sleep(0)
            if self.refuse:
                self.refuse -= 1
                raise httpx.ConnectError("qmd is not listening")
            if self.fail:
                self.fail -= 1
                raise httpx.ReadError("qmd is gone")
            if self.break_search:
                self.qmd.broken_searches += 1
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": {"results": []}}})
            return httpx.Response(self.status, json=ANSWER)
        finally:
            self.running -= 1


def call(body=None):
    return Call("POST", json.dumps(body or SEARCH).encode(), {})


class Routed:
    def __init__(self, ready=True, **settings):
        self.settings = settings
        self.ready = ready

    async def __aenter__(self):
        self.qmd = Qmd(self.ready)
        self.upstream = Upstream(self.qmd)
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(self.upstream))
        router = Router(self.qmd, self.client)
        for name, value in self.settings.items():
            setattr(router, name, value)
        return router, self.qmd, self.upstream

    async def __aexit__(self, *exc):
        await self.client.aclose()


def run(coroutine):
    asyncio.run(asyncio.wait_for(coroutine, 5))


def test_search_reaches_qmd_and_returns_its_answer():
    async def exercise():
        async with Routed() as (router, qmd, upstream):
            response = await router.search(call())
            assert response.status_code == 200
            assert json.loads(response.body) == ANSWER
            assert upstream.calls == 1
            assert router.searches == 0
            assert router.search_slots._value == 2

    run(exercise())


def test_only_two_searches_run_at_once_and_others_wait():
    async def exercise():
        async with Routed() as (router, qmd, upstream):
            upstream.block = asyncio.Event()
            searches = [asyncio.create_task(router.search(call())) for _ in range(5)]
            await asyncio.sleep(0.05)
            assert upstream.running == 2
            assert upstream.most_running == 2
            upstream.block.set()
            assert [r.status_code for r in await asyncio.gather(*searches)] == [200] * 5
            assert upstream.calls == 5
            assert upstream.most_running == 2

    run(exercise())


def test_too_many_searches_fail_at_once():
    async def exercise():
        async with Routed(search_limit=3) as (router, qmd, upstream):
            upstream.block = asyncio.Event()
            searches = [asyncio.create_task(router.search(call())) for _ in range(3)]
            await asyncio.sleep(0.02)
            refused = await router.search(call())
            assert refused.status_code == 503
            assert refused.headers["retry-after"] == "30"
            upstream.block.set()
            await asyncio.gather(*searches)
            assert router.searches == 0

    run(exercise())


def test_search_gives_up_before_clients_do_frees_its_slot_and_restarts_a_stuck_qmd():
    async def exercise():
        async with Routed(search_wait=0.05) as (router, qmd, upstream):
            upstream.block = asyncio.Event()
            response = await router.search(call())
            assert response.status_code == 503
            assert router.search_slots._value == 2
            assert router.searches == 0
            assert qmd.restart_needed

    run(exercise())


def test_search_while_qmd_is_down_restarts_nothing():
    async def exercise():
        async with Routed(ready=False, search_wait=0.05) as (router, qmd, upstream):
            assert (await router.search(call())).status_code == 503
            assert not qmd.restart_needed

    run(exercise())


def test_search_waiting_for_a_slot_gives_up_too():
    async def exercise():
        async with Routed(search_wait=0.05) as (router, qmd, upstream):
            await router.search_slots.acquire()
            await router.search_slots.acquire()
            response = await router.search(call())
            assert response.status_code == 503
            assert upstream.calls == 0
            assert not qmd.restart_needed

    run(exercise())


def test_search_late_for_its_slot_is_no_sign_of_a_stuck_qmd():
    async def exercise():
        async with Routed(search_wait=0.2) as (router, qmd, upstream):
            await router.search_slots.acquire()
            await router.search_slots.acquire()
            upstream.block = asyncio.Event()
            search = asyncio.create_task(router.search(call()))
            await asyncio.sleep(0.15)
            router.search_slots.release()
            assert (await search).status_code == 503
            assert upstream.calls == 1
            assert not qmd.restart_needed

    run(exercise())


def test_search_without_gpu_memory_is_an_error_and_not_an_empty_result():
    async def exercise():
        async with Routed() as (router, qmd, upstream):
            upstream.break_search = True
            response = await router.search(call())
            assert response.status_code == 503
            assert b"models unavailable" in response.body

    run(exercise())


def test_search_survives_a_qmd_restart():
    async def exercise():
        async with Routed() as (router, qmd, upstream):
            upstream.fail = 1
            response = await router.search(call())
            assert response.status_code == 200
            assert upstream.calls == 2

    run(exercise())


def test_search_waits_through_the_moments_before_a_restart_shows():
    async def exercise():
        async with Routed() as (router, qmd, upstream):
            upstream.fail = 1
            upstream.refuse = 3
            response = await router.search(call())
            assert response.status_code == 200
            assert upstream.calls == 5

    run(exercise())


def test_search_keeps_a_good_answer_after_an_earlier_failure():
    async def exercise():
        async with Routed() as (router, qmd, upstream):
            answers = iter([httpx.ReadError("qmd is gone"), httpx.Response(200, json=ANSWER)])

            def transport(request):
                answer = next(answers)
                if isinstance(answer, Exception):
                    # A failed warmup comes between this call and the next one.
                    qmd.broken_searches += 1
                    raise answer
                return answer

            router.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
            response = await router.search(call())
            await router.client.aclose()
            assert response.status_code == 200

    run(exercise())


def test_search_that_keeps_crashing_qmd_stops_retrying():
    async def exercise():
        async with Routed() as (router, qmd, upstream):
            upstream.fail = 99
            response = await router.search(call())
            assert response.status_code == 503
            assert upstream.calls == 2

    run(exercise())


def test_search_waits_for_qmd_to_come_up():
    async def exercise():
        async with Routed(ready=False) as (router, qmd, upstream):
            search = asyncio.create_task(router.search(call()))
            await asyncio.sleep(0.02)
            assert upstream.calls == 0
            qmd.ready.set()
            assert (await search).status_code == 200

    run(exercise())


def test_failing_qmd_answers_at_once_so_that_clients_fall_back():
    async def exercise():
        async with Routed(ready=False) as (router, qmd, upstream):
            qmd.failing = True
            assert (await router.search(call())).status_code == 503
            assert (await router.control(call({"method": "tools/list"}))).status_code == 503
            assert upstream.calls == 0

    run(exercise())


def test_qmd_error_answers_pass_through_but_server_errors_retry():
    async def exercise():
        async with Routed(search_wait=0.3) as (router, qmd, upstream):
            upstream.status = 400
            assert (await router.search(call())).status_code == 400
            upstream.status = 500
            assert (await router.search(call())).status_code == 503

    run(exercise())


def test_calls_without_model_use_need_no_search_slot():
    async def exercise():
        async with Routed() as (router, qmd, upstream):
            await router.search_slots.acquire()
            await router.search_slots.acquire()
            response = await router.control(call({"method": "tools/list"}))
            assert response.status_code == 200

    run(exercise())


def test_calls_without_model_use_give_up_when_qmd_stays_down():
    async def exercise():
        async with Routed(ready=False, control_wait=0.02) as (router, qmd, upstream):
            response = await router.control(call({"method": "tools/list"}))
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

    def upstream(request):
        seen.append(request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {"tools": {"listChanged": True}}}})

    qmd, access = Qmd(), Access()
    client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(runtime=qmd, access=access, qmd_client=client)
    with TestClient(app) as test_client:
        yield test_client, seen, qmd, access


def test_gateway_authentication(gateway):
    client, seen, qmd, access = gateway
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
    client, seen, qmd, access = gateway
    access.failure = failure
    response = client.post("/mcp", json={}, headers=MEMBER)
    assert response.status_code == status
    assert response.headers["Retry-After"]
    assert "WWW-Authenticate" not in response.headers
    assert not seen


def test_gateway_limits_clients_by_the_address_caddy_saw(gateway):
    client, seen, qmd, access = gateway
    client.post("/mcp", json={}, headers={**MEMBER, "X-Forwarded-For": "203.0.113.9, 198.51.100.7"})
    assert access.client_address == "198.51.100.7"


def test_gateway_forwards_protocol_headers_but_no_credentials(gateway):
    client, seen, qmd, access = gateway
    response = client.post("/mcp", json={"method": "tools/list"}, headers={
        **MEMBER, "Origin": "https://public.example", "MCP-Protocol-Version": "2026-07-28",
    })
    assert response.status_code == 200
    assert seen[0].headers["MCP-Protocol-Version"] == "2026-07-28"
    assert "authorization" not in seen[0].headers
    assert "origin" not in seen[0].headers


def test_gateway_rewrites_discovery_answers_and_listen_requests_only(gateway):
    client, seen, qmd, access = gateway
    found = client.post("/mcp", json={"method": "server/discover"}, headers=MEMBER)
    assert found.json()["result"]["capabilities"] == {"tools": {}}
    other = client.post("/mcp", json={"method": "tools/list"}, headers=MEMBER)
    assert other.json()["result"]["capabilities"] == {"tools": {"listChanged": True}}
    client.post("/mcp", headers=MEMBER, json={
        "jsonrpc": "2.0", "id": 2, "method": "subscriptions/listen",
        "params": {"notifications": {"toolsListChanged": True}},
    })
    assert json.loads(seen[-1].content)["params"]["notifications"] == {}


def test_gateway_sends_searches_through_the_search_path(gateway):
    client, seen, qmd, access = gateway
    router = client.app.state.router
    original, calls = router.search, []

    async def spy(call):
        calls.append(call)
        return await original(call)

    router.search = spy
    assert client.post("/mcp", json=SEARCH, headers=MEMBER).status_code == 200
    assert client.post("/mcp", json={"method": "tools/list"}, headers=MEMBER).status_code == 200
    assert len(calls) == 1


def test_gateway_rejects_large_bodies_and_passes_malformed_ones_to_qmd(gateway):
    client, seen, qmd, access = gateway
    response = client.post("/mcp", content=b"x" * (1024 * 1024 + 1), headers=MEMBER)
    assert response.status_code == 413
    assert not seen
    assert client.post("/mcp", content=b"not json", headers=MEMBER).status_code == 200
    assert seen[0].content == b"not json"


@pytest.mark.parametrize("state, failing, status", [
    ("ready", False, 200),
    ("warming", False, 200),
    ("restarting", False, 200),
    ("warming", True, 503),
    ("ready", True, 503),
    ("error", False, 503),
    ("starting", False, 503),
])
def test_health_reports_failure_and_no_content_revision(gateway, state, failing, status):
    client, seen, qmd, access = gateway
    qmd.state, qmd.failing = state, failing
    response = client.get("/healthz")
    assert response.status_code == status
    assert response.json()["state"] == state
    assert "revision" not in response.json()
