#!/usr/bin/env python3
"""
Production startup script for Lens Shtar backend on Render.
"""

import os
import uvicorn

if __name__ == "__main__":
    # Render provides PORT environment variable
    port = int(os.environ.get("PORT", 8000))
    
    # Start uvicorn with production settings
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Production: no auto-reload
        workers=1,     # Render web service: single worker
        access_log=True,
        log_level="info"
    )
