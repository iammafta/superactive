"""
Superactive — Call History & Analytics Routes
"""

from typing import Optional
import os

from fastapi import APIRouter, Query, Depends, HTTPException
from loguru import logger

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


@router.delete("/analytics/history")
async def api_clear_analytics(
    user: UserContext = Depends(get_current_user),
):
    """Clear all call history for the tenant."""
    success = await call_logger.clear_analytics(tenant_id=user.tenant_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear history")
    return {"status": "success", "message": "Call history cleared"}


@router.post("/calls/{call_id}/takeover")
async def api_takeover_call(
    call_id: str,
    user: UserContext = Depends(get_current_user),
):
    """Bridge an active AI call to a human operator."""
    active_calls = call_logger.get_active_calls()
    call_info = next((c for c in active_calls if c["call_id"] == call_id and c["tenant_id"] == user.tenant_id), None)
    
    if not call_info:
        raise HTTPException(status_code=404, detail="Call not found or not currently active.")
        
    try:
        from twilio.rest import Client
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )
        
        human_number = os.getenv("TAKEOVER_PHONE_NUMBER", os.getenv("TWILIO_PHONE_NUMBER", ""))
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Transferring you to a live agent, please hold.</Say>
    <Dial>{human_number}</Dial>
</Response>"""
        
        client.calls(call_id).update(twiml=twiml)
        logger.info(f"🚨 Call Takeover initiated for {call_id}: bridged to {human_number}")
        
        from live_monitor import live_monitor
        live_monitor.emit("takeover_initiated", {"call_id": call_id, "human_number": human_number}, call_id=call_id)
        
        return {"status": "success", "message": "Call transferred to human"}
    except Exception as e:
        logger.error(f"Failed to takeover call: {e}")
        raise HTTPException(status_code=500, detail=str(e))
