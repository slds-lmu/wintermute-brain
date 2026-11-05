import importlib.util
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("brain_worker", Path(__file__).parents[1] / "worker.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def git(cwd, *args):
    result = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.org", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def commit(repo, message):
    git(repo, "commit", "--quiet", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def content(tmp_path, monkeypatch):
    root = tmp_path / "content"
    (root / ".git").mkdir(parents=True)
    monkeypatch.setattr(worker, "BRAIN_DIR", root)
    monkeypatch.setattr(worker, "CODE_DIR", tmp_path / "code")
    return root


@pytest.fixture
def code_repo(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "--quiet", "--initial-branch=main")
    commit(upstream, "first")
    git(upstream, "tag", "v0.1.0")
    return upstream


def test_worker_moves_a_shallow_release_checkout_to_the_latest_main(content, code_repo, tmp_path):
    # What the earlier pinned worker left behind on an existing server.
    code = tmp_path / "code"
    git(tmp_path, "clone", "--quiet", "--depth=1", "--branch", "v0.1.0", code_repo.as_uri(), str(code))
    latest = commit(code_repo, "second")
    assert worker.sync_code()
    assert git(code, "rev-parse", "HEAD") == latest


def test_worker_fills_a_new_code_copy_and_keeps_it_current(content, code_repo, tmp_path):
    # The state main() creates on first start.
    code = tmp_path / "code"
    code.mkdir()
    git(code, "init", "--quiet")
    git(code, "remote", "add", "origin", code_repo.as_uri())
    assert worker.sync_code()
    assert git(code, "rev-parse", "HEAD") == git(code_repo, "rev-parse", "HEAD")
    latest = commit(code_repo, "second")
    assert worker.sync_code()
    assert git(code, "rev-parse", "HEAD") == latest


def test_failed_update_stops_the_cycle_from_using_the_code(content, monkeypatch):
    monkeypatch.setattr(worker, "sh", lambda args, *a, **k: subprocess.CompletedProcess(args, 1, "", "no network"))
    assert not worker.sync_code()


def test_search_ready_after_pull_even_when_the_code_is_unavailable(content, monkeypatch):
    monkeypatch.setattr(worker, "pull", lambda: True)
    monkeypatch.setattr(worker, "sync_code", lambda: False)
    monkeypatch.setattr(worker, "queue", lambda: pytest.fail("compile queue read with no valid code"))
    worker.cycle(False)
    assert (content / ".git" / "brain-ready").exists()
