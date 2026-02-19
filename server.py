"""
Superactive -- AI Voice Agent Server
Phase 4: SaaS Foundation

Config-driven agents with tool calling, state machine, call logging,
SQLite database, and JWT authentication.
Route modules handle individual API domains.
"""

import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")

# Pipecat logging (INFO level -- DEBUG floods the event loop)
import logging
logging.basicConfig(level=logging.INFO)

from db import init_db
from routes import all_routers


# ── Lifespan (startup / shutdown) ─────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup, cleanup on shutdown."""
    logger.info("🚀 Superactive starting up...")
    await init_db()
    logger.info("✅ Database ready")
    yield
    logger.info("🛑 Superactive shutting down")


app = FastAPI(title="Superactive", version="4.0", lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────
# In production, lock to the dashboard origin. In dev, allow all.
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "")
allowed_origins = (
    [DASHBOARD_URL] if DASHBOARD_URL
    else ["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all route modules
for router in all_routers:
    app.include_router(router)

# Config
PORT = int(os.getenv("PORT", 8765))

tavily_key = os.getenv("TAVILY_API_KEY")
logger.debug(f"Startup - Tavily Key Present: {bool(tavily_key)}")
if tavily_key:
    logger.debug(f"Tavily Key Prefix: {tavily_key[:8]}...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
