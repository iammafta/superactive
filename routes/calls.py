"""
Superactive — Call History & Analytics Routes
"""

from typing import Optional

from fastapi import APIRouter, Query, Depends

from call_logger import call_logger
from auth import get_current_user, UserContext

router = APIRouter(prefix="/api", tags=["calls"])


@router.get("/calls")
async def api_get_calls(
    days: int = Query(default=7, ge=1, le=90),
    agent_id: Optional[str] = None,
    business_type: Optional[str] = None,
    user: UserContext = Depends(get_current_user),
):
    """Get call history for the current tenant."""
    calls = await call_logger.get_calls(
        tenant_id=user.tenant_id,
        days=days,
        agent_id=agent_id,
        business_type=business_type
    )
    return [c.model_dump() for c in calls]


@router.get("/calls/active")
async def api_get_active_calls(user: UserContext = Depends(get_current_user)):
    """Get currently active calls (for live dashboard)."""
    # Filter active calls by tenant
    all_active = call_logger.get_active_calls()
    return [c for c in all_active if c.get("tenant_id") == user.tenant_id]


@router.get("/analytics")
async def api_get_analytics(
    days: int = Query(default=30, ge=1, le=365),
    user: UserContext = Depends(get_current_user),
):
    """Get aggregated analytics."""
    return await call_logger.get_analytics(tenant_id=user.tenant_id, days=days)
