#!/usr/bin/env python3
"""Print a currently valid GitHub App installation token."""

from brain_server.github_auth import get_token

if __name__ == "__main__":
    print(get_token())
