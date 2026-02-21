"""
Superactive — Health Check Route

Simple health/readiness endpoint for load balancers, Docker, and monitoring.
"""

from fastapi import APIRouter
from loguru import logger

from db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Basic health check — returns 200 if the server is running and DB is reachable."""
    try:
        db = await get_db()
        await db.execute("SELECT 1")
        await db.close()
        db_status = "ok"
    except Exception as e:
        logger.error(f"Health check DB failure: {e}")
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "version": "4.0",
    }
