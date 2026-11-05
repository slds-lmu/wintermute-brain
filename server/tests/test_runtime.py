import asyncio
import fcntl
import json
import os
import signal
import socket
import stat
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fakeredis.aioredis
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brain_server import github_auth
from brain_server.runtime import CpuQmd, QmdRuntime, QueueDemand, live_gpu_requests


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


def test_finished_request_is_not_recreated(tmp_path, monkeypatch):
    gone = tmp_path / "finished.request"
    monkeypatch.setattr(Path, "glob", lambda self, pattern: iter([gone]))
    assert not live_gpu_requests(tmp_path)
    assert not gone.exists()


def test_handoff_stops_qmd_when_a_search_outlasts_the_drain(runtime_environment, monkeypatch):
    async def exercise():
        monkeypatch.setenv("BRAIN_GPU_DRAIN", "0.01")
        runtime = Runtime(Demand())
        runtime.process = Process()
        runtime.ready.set()
        signals = []

        def kill(pid, sig):
            signals.append(sig)
            runtime.process.returncode = -sig

        monkeypatch.setattr(os, "killpg", kill)
        release = asyncio.Event()

        async def search():
            async with runtime.admission():
                await release.wait()

        active = asyncio.create_task(search())
        await asyncio.sleep(0)
        await asyncio.wait_for(runtime.pause(), 1)
        assert signals == [signal.SIGKILL]
        assert runtime.process is None
        release.set()
        await active
        assert runtime.idle.is_set()
        await runtime.client.aclose()

    asyncio.run(exercise())


def test_refresh_is_skipped_while_a_search_outlasts_the_drain(runtime_environment, monkeypatch):
    async def exercise():
        monkeypatch.setenv("BRAIN_GPU_DRAIN", "0.01")
        runtime = QmdRuntime(Demand())
        runtime.ready.set()
        commands = []

        async def command(*args, **kwargs):
            commands.append(args)
            return ""

        runtime.command = command
        release = asyncio.Event()

        async def search():
            async with runtime.admission():
                await release.wait()

        active = asyncio.create_task(search())
        await asyncio.sleep(0)
        await runtime.refresh()
        assert not commands
        assert runtime.last_refresh > 0
        release.set()
        await active
        await runtime.client.aclose()

    asyncio.run(exercise())


def test_coordinator_survives_a_failed_release(runtime_environment, monkeypatch):
    async def exercise():
        monkeypatch.setenv("BRAIN_GPU_POLL", "0")
        runtime = QmdRuntime(Demand())
        steps = []
        pauses = []
        real_sleep = asyncio.sleep

        async def step():
            steps.append(True)
            if len(steps) == 2:
                runtime.stopping = True
            raise RuntimeError("step failed")

        async def pause(state="paused"):
            pauses.append(state)
            if len(pauses) == 1:
                raise ProcessLookupError

        async def no_wait(seconds):
            await real_sleep(0)

        runtime.step = step
        runtime.pause = pause
        monkeypatch.setattr(asyncio, "sleep", no_wait)
        await asyncio.wait_for(runtime.run(), 2)
        assert len(steps) == 2
        assert pauses == ["error", "error", "stopped"]

    asyncio.run(exercise())


FAKE_QMD = """#!/usr/bin/env python3
import http.server, json, os, sys

record = {
    "pid": os.getpid(),
    "pgid": os.getpgid(0),
    "cpu": os.environ.get("QMD_FORCE_CPU"),
    "gpu": os.environ.get("QMD_LLAMA_GPU"),
    "devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
    "parallelism": os.environ.get("QMD_EMBED_PARALLELISM"),
    "expand_threads": os.environ.get("QMD_EXPAND_THREADS"),
    "niceness": os.nice(0),
    "files": [os.readlink("/proc/self/fd/" + fd) for fd in os.listdir("/proc/self/fd")
              if os.path.exists("/proc/self/fd/" + fd)],
    "args": sys.argv[1:],
}
with open(os.environ["FAKE_QMD_LOG"], "a") as log:
    print(json.dumps(record), file=log)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[-1])), Handler).serve_forever()
"""


def alive(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def test_cpu_qmd_is_killed_restarted_and_never_holds_the_gpu_lock(
    runtime_environment, tmp_path, monkeypatch,
):
    binary = tmp_path / "bin" / "qmd"
    binary.parent.mkdir()
    binary.write_text(FAKE_QMD)
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    records = tmp_path / "records"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setenv("PATH", str(binary.parent) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_QMD_LOG", str(records))
    monkeypatch.setenv("BRAIN_CPU_PORT", str(port))

    def started():
        return [json.loads(line) for line in records.read_text().splitlines()]

    async def exercise():
        runtime = QmdRuntime(Demand())
        assert runtime._acquire_gpu()
        cpu = CpuQmd(runtime)
        supervisor = asyncio.create_task(cpu.run())
        try:
            await asyncio.wait_for(cpu.available.wait(), 20)
            first = started()[0]
            assert (first["cpu"], first["gpu"], first["devices"]) == ("1", "false", "")
            assert first["parallelism"] == cpu.parallelism
            assert first["expand_threads"] == cpu.expand_threads
            assert first["niceness"] == int(cpu.nice) + os.nice(0)
            assert first["args"][:2] == ["mcp", "--http"]
            assert first["pgid"] == first["pid"]
            assert not [path for path in first["files"] if "gpu.lock" in path]
            cpu.abort()
            assert not cpu.available.is_set()
            await asyncio.wait_for(cpu.available.wait(), 20)
            assert not alive(first["pid"])
            assert started()[1]["pid"] != first["pid"]
        finally:
            supervisor.cancel()
            await asyncio.gather(supervisor, return_exceptions=True)
            await runtime.pause("stopped")
            await runtime.client.aclose()
        assert not alive(started()[-1]["pid"])

    asyncio.run(exercise())


def test_cpu_qmd_waits_for_the_repository_and_backs_off_after_a_crash(
    runtime_environment, tmp_path, monkeypatch,
):
    async def exercise():
        runtime = QmdRuntime(Demand())
        cpu = CpuQmd(runtime)
        marker = runtime.repo / ".git" / "brain-ready"
        marker.unlink()
        spawned = []
        delays = []
        real_sleep = asyncio.sleep

        async def spawn(*args, **kwargs):
            spawned.append(args)
            process = Process()
            process.returncode = 1
            return process

        async def sleep(seconds):
            delays.append(seconds)
            if seconds == 1:
                marker.touch()
            if len(delays) > 2:
                raise asyncio.CancelledError
            await real_sleep(0)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        monkeypatch.setattr(asyncio, "sleep", sleep)
        monkeypatch.setattr(runtime, "configure", lambda: None)
        with pytest.raises(asyncio.CancelledError):
            await cpu.run()
        assert delays[0] == 1  # no repository yet
        assert spawned and delays[1] == 5  # failed start: back off
        assert not cpu.available.is_set()
        await runtime.client.aclose()

    asyncio.run(exercise())
