import importlib.util
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("brain_worker", Path(__file__).parents[1] / "worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


@pytest.fixture
def content(tmp_path, monkeypatch):
    root = tmp_path / "content"
    (root / ".git").mkdir(parents=True)
    (root / ".brain-version").write_text("v0.1.1\n")
    monkeypatch.setattr(worker, "BRAIN_DIR", root)
    monkeypatch.setattr(worker, "CODE_DIR", tmp_path / "code")
    return root


def test_worker_uses_the_release_pinned_by_content(content, monkeypatch):
    calls = []

    def command(args, *positional, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(worker, "sh", command)
    assert worker.sync_code()
    assert calls[0][-1] == "refs/tags/v0.1.1:refs/tags/v0.1.1"
    assert calls[1][-1] == "refs/tags/v0.1.1"


def test_invalid_version_cannot_become_a_git_option(content, monkeypatch):
    (content / ".brain-version").write_text("--work-tree=/tmp/other")
    monkeypatch.setattr(worker, "sh", lambda *a, **k: pytest.fail("invalid pin invoked git"))
    assert not worker.sync_code()


def test_failed_fetch_does_not_check_out_a_stale_release(content, monkeypatch):
    calls = []

    def command(args, *a, **k):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "fetch failed")

    monkeypatch.setattr(worker, "sh", command)
    assert not worker.sync_code()
    assert len(calls) == 1


def test_search_ready_after_pull_even_when_compile_version_is_unavailable(content, monkeypatch):
    monkeypatch.setattr(worker, "pull", lambda: True)
    monkeypatch.setattr(worker, "sync_code", lambda: False)
    monkeypatch.setattr(worker, "queue", lambda: pytest.fail("compile queue read with no valid code"))
    worker.cycle(False)
    assert (content / ".git" / "brain-ready").exists()
