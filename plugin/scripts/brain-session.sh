#!/usr/bin/env bash
# Hook entry point for the session-digest channel (02 § 2). Claude Code
# calls it on Stop, SessionStart and SessionEnd with the hook JSON on
# stdin. It must return fast, so all real work (reading the transcript,
# the model call, gitleaks, the PR) is forked into the background by
# brain_session.py. Never fails the hook: a broken digest must not block
# the user's session.
set -u
event="${1:-stop}"
# Recursion guard: the digest agent is itself a `claude -p` run; it starts
# with --bare, but belt and braces.
[ "${BRAIN_DIGEST_CHILD:-}" = "1" ] && exit 0
[ "${BRAIN_SESSION_DIGEST:-on}" = "off" ] && exit 0
command -v python3 >/dev/null 2>&1 || exit 0
# Create the log folder first: without it the redirect below fails and the
# hook silently never runs on a fresh machine (live hook test 2026-11-05).
logdir="${XDG_CACHE_HOME:-$HOME/.cache}/brain"
mkdir -p "$logdir" 2>/dev/null || exit 0
python3 "$(dirname "$0")/brain_session.py" "$event" 2>>"$logdir/hook.log" || true
exit 0
