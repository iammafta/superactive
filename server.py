"""
Superactive -- AI Voice Agent Server
Phase 4: SaaS Foundation

Config-driven agents with tool calling, state machine, call logging,
PostgreSQL database, and JWT authentication.
Route modules handle individual API domains.
"""

import os
import sys
from contextlib import asynccontextmanager
import asyncio

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")

# Pipecat logging (INFO level -- DEBUG floods the event loop)
import logging
logging.basicConfig(level=logging.INFO)

from telemetry import init_telemetry
init_telemetry("superactive-backend")

from routes import all_routers
from rate_limit import limiter


# ── Lifespan (startup / shutdown) ─────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and Redis on startup, cleanup on shutdown."""
    from db import init_db, get_pool
    from redis_client import init_redis, close_redis
    from live_monitor import live_monitor

    logger.info("🚀 Superactive starting up...")
    
    # Init DB
    await init_db()
    logger.info("✅ Database ready")
    
    # Init Redis
    await init_redis()
    
    # Start Redis Pub/Sub listener for WebSockets
    app.state.monitor_task = asyncio.create_task(live_monitor.listen_to_redis())
    logger.info("✅ LiveMonitor Pub/Sub ready")
    
    yield
    
    logger.info("🛑 Superactive shutting down")
    
    # Stop Pub/Sub listener
    if hasattr(app.state, "monitor_task"):
        app.state.monitor_task.cancel()
    pool = await get_pool()
    if pool:
        await pool.close()
    
    import db
    db._pool = None
    
    await close_redis()

app = FastAPI(title="Superactive", version="4.0", lifespan=lifespan)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
FastAPIInstrumentor.instrument_app(app)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
