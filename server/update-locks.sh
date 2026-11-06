#!/bin/sh
# Regenerate the server's lock files, taking nothing uploaded in the last 14
# days: a compromised release has time to be found. Run from the repository root.
# Arguments go to uv, e.g. --upgrade or --upgrade-package NAME. See server/README.md.
set -eu
cutoff="$(date -u -d "${BRAIN_LOCK_MIN_AGE_DAYS:-14} days ago" +%Y-%m-%dT%H:%M:%SZ)"
compile="uv pip compile --universal --python-version 3.10 --generate-hashes --no-header --exclude-newer $cutoff"
$compile server/requirements.txt -o server/requirements.lock "$@"
# The tests run on the versions the image installs.
$compile server/requirements-dev.txt -c server/requirements.lock -o server/requirements-dev.lock "$@"
