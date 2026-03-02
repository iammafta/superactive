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
from db import db_get_tenant, db_update_tenant, db_generate_api_key

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsUpdate(BaseModel):
    business_name: str | None = None
    owner_email: str | None = None
    public_url: str | None = None
    telephony_provider: str | None = None
    backup_provider: str | None = None
    telnyx_api_key: str | None = None
    telnyx_connection_id: str | None = None
    telnyx_phone: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone: str | None = None
    webhook_url: str | None = None


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

    # Telnyx: DB-first, env fallback
    telnyx_api_key = tenant.get("telnyx_api_key") or os.getenv("TELNYX_API_KEY", "")
    telnyx_connection_id = tenant.get("telnyx_connection_id") or os.getenv("TELNYX_CONNECTION_ID", "")
    telnyx_phone_val = tenant.get("telnyx_phone") or os.getenv("TELNYX_PHONE_NUMBER", "")

    # Twilio: DB-first, env fallback
    twilio_account_sid = tenant.get("twilio_account_sid") or os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token = tenant.get("twilio_auth_token") or os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_phone_val = tenant.get("twilio_phone") or os.getenv("TWILIO_PHONE_NUMBER", "")

    gcp_project = os.getenv("GCP_PROJECT_ID", "")
    gcp_location = os.getenv("GCP_LOCATION", "")

    return {
        # Editable
        "business_name": tenant.get("name", ""),
        "owner_email": tenant.get("email", ""),
        "public_url": tenant.get("public_url", ""),
        "telephony_provider": tenant.get("telephony_provider", "telnyx"),
        "backup_provider": tenant.get("backup_provider", ""),
        # Telnyx (editable, but masked on read)
        "telnyx_api_key_masked": _mask(telnyx_api_key),
        "telnyx_connection_id_masked": _mask(telnyx_connection_id),
        "telnyx_phone": telnyx_phone_val,
        "has_custom_telnyx": bool(tenant.get("telnyx_api_key")),
        # Twilio (editable, but masked on read)
        "twilio_account_sid_masked": _mask(twilio_account_sid),
        "twilio_auth_token_masked": _mask(twilio_auth_token),
        "twilio_phone": twilio_phone_val,
        "has_custom_twilio": bool(tenant.get("twilio_account_sid")),
        # Webhooks & API Keys
        "webhook_url": tenant.get("webhook_url", ""),
        "api_key_masked": _mask(tenant.get("api_key", "")),
        "has_api_key": bool(tenant.get("api_key")),
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
    if body.telephony_provider is not None:
        updates["telephony_provider"] = body.telephony_provider
    if body.backup_provider is not None:
        updates["backup_provider"] = body.backup_provider
    if body.telnyx_api_key is not None:
        updates["telnyx_api_key"] = body.telnyx_api_key
    if body.telnyx_connection_id is not None:
        updates["telnyx_connection_id"] = body.telnyx_connection_id
    if body.telnyx_phone is not None:
        updates["telnyx_phone"] = body.telnyx_phone
    if body.twilio_account_sid is not None:
        updates["twilio_account_sid"] = body.twilio_account_sid
    if body.twilio_auth_token is not None:
        updates["twilio_auth_token"] = body.twilio_auth_token
    if body.twilio_phone is not None:
        updates["twilio_phone"] = body.twilio_phone
    if body.webhook_url is not None:
        updates["webhook_url"] = body.webhook_url

    if not updates:
        return {"status": "no_changes"}

    success = await db_update_tenant(user.tenant_id, **updates)
    if not success:
         raise HTTPException(status_code=500, detail="Failed to update settings")

    return {"status": "saved"}

@router.post("/settings/api-key/roll")
async def roll_api_key(user: UserContext = Depends(get_current_user)):
    """Generate and return a new API key. The full key is ONLY returned this ONE time."""
    new_key = await db_generate_api_key(user.tenant_id)
    if not new_key:
        raise HTTPException(status_code=500, detail="Failed to generate API Key")
    
    return {"api_key": new_key}
