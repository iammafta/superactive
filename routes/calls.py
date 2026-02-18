"""
Superactive — Call History & Analytics Routes
"""

from typing import Optional

from fastapi import APIRouter, Query

from call_logger import call_logger

router = APIRouter(prefix="/api", tags=["calls"])


@router.get("/calls")
async def api_get_calls(
    days: int = Query(default=7, ge=1, le=90),
    agent_id: Optional[str] = None,
    business_type: Optional[str] = None,
):
    """Get call history."""
    calls = await call_logger.get_calls(days=days, agent_id=agent_id, business_type=business_type)
    return [c.model_dump() for c in calls]


@router.get("/calls/active")
async def api_get_active_calls():
    """Get currently active calls (for live dashboard)."""
    return call_logger.get_active_calls()


@router.get("/analytics")
async def api_get_analytics(days: int = Query(default=30, ge=1, le=365)):
    """Get aggregated analytics."""
    return await call_logger.get_analytics(days=days)
