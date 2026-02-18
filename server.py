"""
Superactive — AI Voice Agent Server
Phase 3: Configurable Agent Platform

Config-driven agents with tool calling, state machine, and call logging.
Route modules handle individual API domains.
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")

# Pipecat logging (INFO level — DEBUG floods the event loop)
import logging
logging.basicConfig(level=logging.INFO)

from routes import all_routers

app = FastAPI(title="Superactive", version="3.0")

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
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
