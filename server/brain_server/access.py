"""GitHub token authorization with bounded use of the GitHub API."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time

import httpx

log = logging.getLogger(__name__)

# GitHub documents tokens of up to 255 characters from this alphabet. Anything
# else cannot be valid and must not cost a failed login against the GitHub API.
TOKEN_FORMAT = re.compile(r"[A-Za-z0-9_]{20,255}")


class GitHubUnavailable(Exception):
    """GitHub gave no permission decision; the token's validity is unknown."""


class ChecksThrottled(Exception):
    """This client requested too many checks of tokens not yet in the cache."""


def _rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    if response.status_code != 403:
        return False
    if response.headers.get("retry-after") or response.headers.get("x-ratelimit-remaining") == "0":
        return True
    message = response.text.lower()
    return any(text in message for text in ("rate limit", "abuse", "login attempts"))


def _denied(response: httpx.Response, statuses: frozenset[int]) -> bool:
    """Return True for a real denial; raise when GitHub did not decide."""
    if _rate_limited(response):
        raise GitHubUnavailable(f"GitHub rate limit ({response.status_code})")
    if response.status_code in statuses:
        return True
    if response.status_code != 200:
        raise GitHubUnavailable(f"GitHub answered {response.status_code}")
    return False


USER_DENIED = frozenset({401, 403})
REPO_DENIED = frozenset({401, 403, 404})


class RepoAccess:
    """Decide whether a token may read the repository.

    Only decisions from GitHub are cached. While GitHub cannot decide, a token
    that was recently allowed keeps working for stale_grace seconds. Requests
    for tokens not in the cache are limited per client and in total, because
    every one of them would otherwise reach GitHub without authentication.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        repo: str,
        allow_ttl: float = 300,
        deny_ttl: float = 30,
        stale_grace: float = 3600,
        checks_per_minute: int = 30,
        max_concurrent: int = 8,
        max_pending: int = 64,
    ) -> None:
        self.client = client
        self.repo = repo
        self.allow_ttl = allow_ttl
        self.deny_ttl = deny_ttl
        self.stale_grace = stale_grace
        self.checks_per_minute = checks_per_minute
        self.max_pending = max_pending
        self.cache: dict[str, tuple[float, bool]] = {}
        self.pending: dict[str, asyncio.Task] = {}
        self.windows: dict[str, tuple[float, int]] = {}
        self.concurrency = asyncio.Semaphore(max_concurrent)

    async def allowed(self, token: str, client_address: str = "") -> bool:
        if not TOKEN_FORMAT.fullmatch(token):
            return False
        digest = hashlib.sha256(token.encode()).hexdigest()
        now = time.monotonic()
        hit = self.cache.get(digest)
        if hit and hit[0] > now:
            return hit[1]
        stale = bool(hit and hit[1] and hit[0] + self.stale_grace > now)
        task = self.pending.get(digest)
        if task is None:
            # A known token is always rechecked, so that throttling cannot
            # keep a revoked one alive through the stale grace period.
            if not stale:
                self._admit_check(client_address, now)
            task = asyncio.create_task(self._check(digest, token))
            self.pending[digest] = task
            task.add_done_callback(lambda _: self.pending.pop(digest, None))
        try:
            return await asyncio.shield(task)
        except GitHubUnavailable as error:
            if stale:
                log.warning("Using a cached permission decision: %s", error)
                return True
            raise

    def _admit_check(self, client_address: str, now: float) -> None:
        if len(self.pending) >= self.max_pending:
            raise GitHubUnavailable("Too many permission checks in progress")
        if len(self.windows) >= 4096:
            self.windows = {k: v for k, v in self.windows.items() if v[0] + 60 > now}
            if len(self.windows) >= 4096:
                raise GitHubUnavailable("Too many clients with permission checks")
        started, count = self.windows.get(client_address, (now, 0))
        if started + 60 <= now:
            started, count = now, 0
        if count >= self.checks_per_minute:
            raise ChecksThrottled
        self.windows[client_address] = (started, count + 1)

    async def _check(self, digest: str, token: str) -> bool:
        async with self.concurrency:
            try:
                allowed = await self._ask_github(token)
            except httpx.HTTPError as error:
                raise GitHubUnavailable(type(error).__name__) from error
        self._remember(digest, allowed)
        return allowed

    async def _ask_github(self, token: str) -> bool:
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "User-Agent": "wintermute-brain-search",
        }
        user = await self.client.get("https://api.github.com/user", headers=headers)
        if _denied(user, USER_DENIED):
            return False
        repo = await self.client.get("https://api.github.com/repos/" + self.repo, headers=headers)
        if _denied(repo, REPO_DENIED):
            return False
        try:
            return repo.json().get("permissions", {}).get("pull") is True
        except (ValueError, AttributeError) as error:
            raise GitHubUnavailable("Malformed GitHub response") from error

    def _remember(self, digest: str, allowed: bool) -> None:
        now = time.monotonic()
        if len(self.cache) >= 1024:
            self.cache = {
                k: v for k, v in self.cache.items()
                if v[0] + (self.stale_grace if v[1] else 0) > now
            }
            if len(self.cache) >= 1024:
                self.cache.pop(next(iter(self.cache)))
        self.cache[digest] = (now + (self.allow_ttl if allowed else self.deny_ttl), allowed)
