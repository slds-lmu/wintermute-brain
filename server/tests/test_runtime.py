import asyncio
import json
import os
import socket
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brain_server import github_auth
from brain_server.runtime import (
    BROKEN_SEARCH,
    DEGRADED_SEARCH,
    REQUEST_LINE,
    QmdRuntime,
)


@pytest.fixture
def runtime_environment(tmp_path, monkeypatch):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    (tmp_path / "repo" / ".git" / "brain-ready").touch()
    monkeypatch.setenv("BRAIN_DIR", str(tmp_path / "repo"))
    monkeypatch.setenv("BRAIN_QMD_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("BRAIN_QMD_POLL", "0.01")


FAKE_QMD = """#!/usr/bin/env python3
import http.server, json, os, sys

directory = os.environ["FAKE_QMD_DIR"]
record = {
    "pid": os.getpid(),
    "pgid": os.getpgid(0),
    "service_token": os.environ.get("BRAIN_SEARCH_SERVICE_TOKEN"),
    "args": sys.argv[1:],
}
with open(directory + "/starts", "a") as log:
    print(json.dumps(record), file=log)
print("server log line", flush=True)


class Handler(http.server.BaseHTTPRequestHandler):
    def reply(self, body):
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(b"{}")

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        print("12:00:00.000 POST /mcp tools/call query \\"private question\\" (1ms)", flush=True)
        if os.path.exists(directory + "/no-memory"):
            print("Batch embedding error: Error: Failed to create any embedding context", flush=True)
        if os.path.exists(directory + "/low-memory"):
            print("Structured query expansion failed: InsufficientMemoryError: too large", flush=True)
        self.reply(json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode())

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[-1])), Handler).serve_forever()
"""


def alive(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


@pytest.fixture
def fake_qmd(runtime_environment, tmp_path, monkeypatch):
    binary = tmp_path / "bin" / "node"
    binary.parent.mkdir()
    binary.write_text(FAKE_QMD)
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setenv("PATH", str(binary.parent) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_QMD_DIR", str(tmp_path))
    monkeypatch.setenv("BRAIN_QMD_ENTRY", "/fake/qmd.js")
    monkeypatch.setenv("BRAIN_QMD_PORT", str(port))
    monkeypatch.setenv("BRAIN_SEARCH_SERVICE_TOKEN", "internal-service-token")
    (tmp_path / "starts").touch()
    return tmp_path


def starts(directory):
    return [json.loads(line) for line in (directory / "starts").read_text().splitlines()]


async def no_command(*args, **kwargs):
    return "revision"


async def until(condition, timeout=20):
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError(condition)
        await asyncio.sleep(0.01)


def test_qmd_starts_directly_without_the_service_token_and_restarts_after_a_crash(fake_qmd):
    async def exercise():
        runtime = QmdRuntime()
        runtime.command = no_command
        task = asyncio.create_task(runtime.run())
        try:
            await asyncio.wait_for(runtime.ready.wait(), 20)
            first = starts(fake_qmd)[0]
            assert first["args"][:3] == ["/fake/qmd.js", "mcp", "--http"]
            assert first["service_token"] is None
            assert first["pgid"] == first["pid"]
            assert runtime.state == "ready"
            os.kill(first["pid"], 9)
            await until(lambda: len(starts(fake_qmd)) == 2)
            await asyncio.wait_for(runtime.ready.wait(), 20)
            await until(lambda: runtime.state == "ready")
            assert not runtime.status()["failing"]
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        assert not alive(starts(fake_qmd)[-1]["pid"])

    asyncio.run(exercise())


def test_lack_of_gpu_memory_restarts_qmd_and_stays_visible_until_it_fits(fake_qmd, monkeypatch):
    async def exercise():
        runtime = QmdRuntime()
        runtime.command = no_command
        real_sleep = asyncio.sleep

        async def short_sleep(seconds):
            await real_sleep(min(seconds, 0.05))

        monkeypatch.setattr(asyncio, "sleep", short_sleep)
        task = asyncio.create_task(runtime.run())
        try:
            await asyncio.wait_for(runtime.ready.wait(), 20)
            (fake_qmd / "no-memory").touch()
            response = await runtime.client.post(runtime.upstream + "/mcp", json={})
            assert response.status_code == 200
            await until(lambda: runtime.broken_searches >= 1)
            # The restart's warmup finds the same lack of memory.
            await until(lambda: runtime.status()["failing"])
            assert not runtime.ready.is_set()
            assert len(starts(fake_qmd)) >= 2
            (fake_qmd / "no-memory").unlink()
            await until(lambda: runtime.ready.is_set() and not runtime.status()["failing"])
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def test_warmup_accepts_no_partial_load_but_a_running_qmd_keeps_serving(fake_qmd, monkeypatch):
    async def exercise():
        runtime = QmdRuntime()
        runtime.command = no_command
        real_sleep = asyncio.sleep

        async def short_sleep(seconds):
            await real_sleep(min(seconds, 0.05))

        monkeypatch.setattr(asyncio, "sleep", short_sleep)
        (fake_qmd / "low-memory").touch()
        task = asyncio.create_task(runtime.run())
        try:
            await until(lambda: runtime.status()["failing"])
            assert not runtime.ready.is_set()
            (fake_qmd / "low-memory").unlink()
            await until(lambda: runtime.ready.is_set() and not runtime.status()["failing"])
            started = len(starts(fake_qmd))
            (fake_qmd / "low-memory").touch()
            response = await runtime.client.post(runtime.upstream + "/mcp", json={})
            assert response.status_code == 200
            await until(lambda: runtime.degraded_searches >= 2)
            await real_sleep(0.1)
            assert runtime.ready.is_set()
            assert len(starts(fake_qmd)) == started
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def test_query_text_stays_out_of_the_log(fake_qmd, capfd):
    async def exercise():
        runtime = QmdRuntime()
        runtime.command = no_command
        task = asyncio.create_task(runtime.run())
        try:
            await asyncio.wait_for(runtime.ready.wait(), 20)
            await runtime.client.post(runtime.upstream + "/mcp", json={})
            await asyncio.sleep(0.1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
    output = capfd.readouterr().out
    assert "server log line" in output
    assert "private question" not in output


def test_log_patterns_match_qmds_real_messages():
    assert BROKEN_SEARCH.search("Batch embedding error: Error: Failed to create any embedding context")
    assert BROKEN_SEARCH.search("Reranker unavailable — skipping reranking (InsufficientMemoryError).")
    assert DEGRADED_SEARCH.search("Structured query expansion failed: InsufficientMemoryError: A context size of 2048 is too large")
    assert not BROKEN_SEARCH.search("QMD MCP server listening on http://127.0.0.1:8182/mcp")
    assert REQUEST_LINE.match('01:57:14.732 POST /mcp tools/call query "secret" (9324ms)')
    assert REQUEST_LINE.match("18:37:45.939 GET /health (5ms)")
    assert not REQUEST_LINE.match("Structured query expansion failed")


def test_stop_survives_a_process_that_just_exited(runtime_environment, monkeypatch):
    class JustExited:
        pid = 1
        returncode = None

        async def wait(self):
            return 0

    def gone(*args):
        raise ProcessLookupError

    async def exercise():
        runtime = QmdRuntime()
        runtime.process = JustExited()
        monkeypatch.setattr(os, "killpg", gone)
        await runtime.stop("restarting")
        assert runtime.process is None
        await runtime.client.aclose()

    asyncio.run(exercise())


def test_log_watcher_survives_a_line_beyond_its_buffer(runtime_environment):
    async def exercise():
        runtime = QmdRuntime()
        stream = asyncio.StreamReader(limit=64)
        stream.feed_data(b"x" * 1000 + b"\n")
        stream.feed_data(b"Reranker unavailable\n")
        stream.feed_eof()
        await runtime.watch_log(stream)
        assert runtime.broken_searches == 1
        assert runtime.restart_needed
        await runtime.client.aclose()

    asyncio.run(exercise())


def test_waits_for_the_repository(runtime_environment, tmp_path):
    async def exercise():
        (tmp_path / "repo" / ".git" / "brain-ready").unlink()
        runtime = QmdRuntime()
        await runtime.step()
        assert runtime.state == "waiting_for_repository"
        assert not runtime.ready.is_set()
        await runtime.client.aclose()

    asyncio.run(exercise())


def test_refresh_runs_beside_a_ready_qmd_and_a_failure_keeps_it_serving(runtime_environment, monkeypatch):
    async def exercise():
        monkeypatch.setenv("BRAIN_INDEX_POLL", "0.01")
        runtime = QmdRuntime()
        runtime.ready.set()
        # A failure of any kind must not end the refreshing.
        outcomes = iter([UnicodeDecodeError("utf-8", b"x", 0, 1, "bad output"), "revision", "revision"])
        states = []

        async def command(*args, **kwargs):
            states.append(runtime.ready.is_set())
            outcome = next(outcomes, "revision")
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        runtime.command = command
        refresher = asyncio.create_task(runtime.refresh_loop())
        await until(lambda: runtime.refresh_failing)
        assert runtime.status()["failing"]
        assert runtime.ready.is_set()
        await until(lambda: not runtime.refresh_failing)
        refresher.cancel()
        await asyncio.gather(refresher, return_exceptions=True)
        assert all(states)
        await runtime.client.aclose()

    asyncio.run(exercise())


def test_pull_during_indexing_is_refreshed_on_the_next_pass(runtime_environment):
    async def exercise():
        runtime = QmdRuntime()
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
