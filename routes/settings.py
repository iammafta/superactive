"""
Superactive — Settings Routes

GET  /api/settings  → Returns editable + read-only (masked) settings
PUT  /api/settings  → Saves only editable fields to DB
"""

import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger

from auth import get_current_user, UserContext
from db import db_get_tenant, db_update_tenant

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsUpdate(BaseModel):
    business_name: str | None = None
    owner_email: str | None = None
    public_url: str | None = None
    twilio_sid: str | None = None
    twilio_token: str | None = None
    twilio_phone: str | None = None


def _mask(value: str, reveal: int = 4) -> str:
    """Mask a string, keeping first 2 and last `reveal` chars visible."""
    if not value or len(value) <= 6:
        return "••••"
    return f"{value[:2]}{'•' * (len(value) - 2 - reveal)}{value[-reveal:]}"


@router.get("/settings")
async def get_settings(user: UserContext = Depends(get_current_user)):
    """Return all settings for the current tenant."""
    tenant = await db_get_tenant(user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Twilio: DB-first, env fallback
    twilio_sid = tenant.get("twilio_sid") or os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token = tenant.get("twilio_token") or os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_phone_val = tenant.get("twilio_phone") or os.getenv("TWILIO_PHONE_NUMBER", "")
    gcp_project = os.getenv("GCP_PROJECT_ID", "")
    gcp_location = os.getenv("GCP_LOCATION", "")

    return {
        # Editable
        "business_name": tenant.get("name", ""),
        "owner_email": tenant.get("email", ""),
        "public_url": tenant.get("public_url", ""),
        # Twilio (editable, but masked on read)
        "twilio_sid_masked": _mask(twilio_sid),
        "twilio_token_masked": _mask(twilio_token),
        "twilio_phone": twilio_phone_val,
        "has_custom_twilio": bool(tenant.get("twilio_sid")),
        # Read-only
        "gcp_project": gcp_project,
        "gcp_location": gcp_location,
        "plan": tenant.get("plan", "starter"),
    }


@router.put("/settings")
async def update_settings(body: SettingsUpdate, user: UserContext = Depends(get_current_user)):
    """Update only the editable settings fields."""
    updates = {}
    if body.business_name is not None:
        updates["name"] = body.business_name
    if body.owner_email is not None:
        updates["email"] = body.owner_email
    if body.public_url is not None:
        updates["public_url"] = body.public_url
    if body.twilio_sid is not None:
        updates["twilio_sid"] = body.twilio_sid
    if body.twilio_token is not None:
        updates["twilio_token"] = body.twilio_token
    if body.twilio_phone is not None:
        updates["twilio_phone"] = body.twilio_phone

    if not updates:
        return {"status": "no_changes"}

    success = await db_update_tenant(user.tenant_id, **updates)
    if not success:
         raise HTTPException(status_code=500, detail="Failed to update settings")

    return {"status": "saved"}
