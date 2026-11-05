import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brain_server.access import ChecksThrottled, GitHubUnavailable, RepoAccess

TOKEN = "ghp_" + "a" * 36
ALLOWED = {"permissions": {"pull": True}}


def github(user=None, repo=None, calls=None):
    """user and repo are responses or callables; both default to allowing."""

    def handler(request):
        if calls is not None:
            calls.append(request.url.path)
        answer = user if request.url.path == "/user" else repo
        if callable(answer):
            answer = answer()
        if answer is None:
            answer = httpx.Response(200, json={"login": "member"} if request.url.path == "/user" else ALLOWED)
        return answer

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.mark.parametrize("permission, expected", [(True, True), (False, False)])
def test_repository_permission_decides_and_is_cached_by_hash(permission, expected):
    async def exercise():
        calls = []
        repo = httpx.Response(200, json={"permissions": {"pull": permission}})
        async with github(repo=repo, calls=calls) as client:
            access = RepoAccess(client, "org/repo")
            assert await access.allowed(TOKEN) is expected
            assert await access.allowed(TOKEN) is expected
            assert len(calls) == 2
            assert TOKEN not in repr(access.cache)

    run(exercise())


@pytest.mark.parametrize("user, repo", [
    (httpx.Response(401), None),
    (httpx.Response(403, json={"message": "Resource not accessible"}), None),
    (None, httpx.Response(401)),
    (None, httpx.Response(403, json={"message": "SAML enforcement"})),
    (None, httpx.Response(404)),
])
def test_real_denials_are_cached(user, repo):
    async def exercise():
        calls = []
        async with github(user, repo, calls) as client:
            access = RepoAccess(client, "org/repo")
            assert await access.allowed(TOKEN) is False
            before = len(calls)
            assert await access.allowed(TOKEN) is False
            assert len(calls) == before

    run(exercise())


@pytest.mark.parametrize("user, repo", [
    (httpx.Response(500), None),
    (httpx.Response(502), None),
    (None, httpx.Response(503)),
    (httpx.Response(429), None),
    (None, httpx.Response(429)),
    (httpx.Response(403, headers={"retry-after": "60"}), None),
    (httpx.Response(403, headers={"x-ratelimit-remaining": "0"}), None),
    (httpx.Response(403, json={"message": "API rate limit exceeded"}), None),
    (None, httpx.Response(403, json={"message": "You have triggered an abuse detection mechanism"})),
    (httpx.Response(403, json={"message": "Maximum number of login attempts exceeded"}), None),
    (None, httpx.Response(200, text="not json")),
    (None, httpx.Response(301)),
])
def test_missing_github_decisions_are_not_cached_as_denials(user, repo):
    async def exercise():
        calls = []
        async with github(user, repo, calls) as client:
            access = RepoAccess(client, "org/repo")
            with pytest.raises(GitHubUnavailable):
                await access.allowed(TOKEN)
            assert not access.cache
            before = len(calls)
            with pytest.raises(GitHubUnavailable):
                await access.allowed(TOKEN)
            assert len(calls) > before

    run(exercise())


def test_network_failure_is_no_decision():
    async def exercise():
        def fail():
            raise httpx.ConnectError("down")

        async with github(fail) as client:
            with pytest.raises(GitHubUnavailable):
                await RepoAccess(client, "org/repo").allowed(TOKEN)

    run(exercise())


def test_recently_allowed_token_survives_a_github_outage():
    async def exercise():
        outage = {"on": False}

        def user():
            return httpx.Response(503) if outage["on"] else httpx.Response(200, json={})

        async with github(user) as client:
            access = RepoAccess(client, "org/repo", allow_ttl=-1, stale_grace=3600)
            assert await access.allowed(TOKEN) is True
            outage["on"] = True
            assert await access.allowed(TOKEN) is True
            digest, (expires, allowed) = next(iter(access.cache.items()))
            access.cache[digest] = (expires - 7200, allowed)
            with pytest.raises(GitHubUnavailable):
                await access.allowed(TOKEN)

    run(exercise())


def test_denied_token_does_not_survive_a_github_outage():
    async def exercise():
        outage = {"on": False}

        def user():
            return httpx.Response(503) if outage["on"] else httpx.Response(401)

        async with github(user) as client:
            access = RepoAccess(client, "org/repo", deny_ttl=-1)
            assert await access.allowed(TOKEN) is False
            outage["on"] = True
            with pytest.raises(GitHubUnavailable):
                await access.allowed(TOKEN)

    run(exercise())


@pytest.mark.parametrize("token", ["short", "x" * 256, "has space" + "a" * 20, "ghp_" + "é" * 30])
def test_impossible_tokens_never_reach_github(token):
    async def exercise():
        calls = []
        async with github(calls=calls) as client:
            assert await RepoAccess(client, "org/repo").allowed(token) is False
            assert not calls

    run(exercise())


def test_new_tokens_are_limited_per_client_but_known_tokens_are_not():
    async def exercise():
        async with github(httpx.Response(401)) as client:
            access = RepoAccess(client, "org/repo", checks_per_minute=2)
            first, second, third = (f"ghp_{index}" + "a" * 36 for index in range(3))
            await access.allowed(first, "198.51.100.1")
            await access.allowed(second, "198.51.100.1")
            with pytest.raises(ChecksThrottled):
                await access.allowed(third, "198.51.100.1")
            # A cached decision costs GitHub nothing.
            assert await access.allowed(first, "198.51.100.1") is False
            # Another address has its own budget.
            assert await access.allowed(third, "198.51.100.2") is False

    run(exercise())


def test_throttled_client_keeps_a_token_it_recently_used():
    async def exercise():
        async with github() as client:
            access = RepoAccess(client, "org/repo", allow_ttl=-1, checks_per_minute=1)
            assert await access.allowed(TOKEN, "198.51.100.1") is True
            assert await access.allowed(TOKEN, "198.51.100.1") is True

    run(exercise())


def test_throttling_cannot_keep_a_revoked_token_alive():
    async def exercise():
        revoked = {"value": False}

        def user():
            return httpx.Response(401) if revoked["value"] else httpx.Response(200, json={})

        async with github(user) as client:
            access = RepoAccess(client, "org/repo", allow_ttl=-1, checks_per_minute=1)
            assert await access.allowed(TOKEN, "198.51.100.1") is True
            revoked["value"] = True
            assert await access.allowed(TOKEN, "198.51.100.1") is False

    run(exercise())


def test_concurrent_requests_for_one_token_share_one_check():
    async def exercise():
        calls = []
        async with github(calls=calls) as client:
            access = RepoAccess(client, "org/repo")
            results = await asyncio.gather(*(access.allowed(TOKEN) for _ in range(20)))
            assert all(results)
            assert len(calls) == 2
            assert not access.pending

    run(exercise())


def test_checks_in_progress_are_bounded():
    async def exercise():
        release = asyncio.Event()

        async def handler(request):
            await release.wait()
            return httpx.Response(401)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            access = RepoAccess(client, "org/repo", max_concurrent=1, max_pending=2, checks_per_minute=100)
            tokens = [f"ghp_{index}" + "a" * 36 for index in range(3)]
            waiting = [asyncio.create_task(access.allowed(token)) for token in tokens[:2]]
            await asyncio.sleep(0)
            with pytest.raises(GitHubUnavailable):
                await access.allowed(tokens[2])
            release.set()
            assert await asyncio.gather(*waiting) == [False, False]

    run(exercise())
