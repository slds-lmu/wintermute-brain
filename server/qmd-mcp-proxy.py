#!/usr/bin/env python3
"""Start the authenticated gateway and qmd lifecycle coordinator."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("brain_server.app:app", host="0.0.0.0", port=8181, access_log=False)
