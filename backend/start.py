#!/usr/bin/env python3
"""
Lens Shtar — Local Demo Backend Runner
=======================================
Starts the FastAPI backend locally.

Usage:
    python start.py               # production-style (no reload)
    RELOAD=true python start.py   # development / demo (auto-reload on file changes)
    PORT=9000 python start.py     # run on a custom port
"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    reload = os.environ.get("RELOAD", "false").lower() in ("1", "true", "yes")
    host = os.environ.get("HOST", "0.0.0.0")

    print(f"\n{'='*54}")
    print(f"  Lens Shtar Backend — Local Demo")
    print(f"{'='*54}")
    print(f"  Listening : http://{host}:{port}")
    print(f"  Health    : http://localhost:{port}/api/health")
    print(f"  Reload    : {'enabled' if reload else 'disabled'}")
    print(f"{'='*54}\n")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=1,
        access_log=True,
        log_level="info",
    )
