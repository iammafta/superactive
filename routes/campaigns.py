"""
Superactive — Campaign Routes
"""

import csv
import io
import re

from fastapi import APIRouter, HTTPException, UploadFile, File as FastAPIFile, Depends
from loguru import logger

from auth import get_current_user, UserContext
from agent_config import load_agent
from campaign_config import (
    CampaignConfig as CampaignModel,
    ContactRecord,
    load_campaign, save_campaign, list_campaigns, delete_campaign,
)
from campaign_dialer import CampaignDialer, get_active_dialer

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

_E164_RE = re.compile(r'^\+[1-9]\d{1,14}$')


@router.get("")
async def api_list_campaigns(user: UserContext = Depends(get_current_user)):
    """List all campaigns for current tenant."""
    campaigns = await list_campaigns(user.tenant_id)
    return [c.model_dump() for c in campaigns]


@router.get("/{campaign_id}")
async def api_get_campaign(campaign_id: str, user: UserContext = Depends(get_current_user)):
    """Get a specific campaign."""
    campaign = await load_campaign(campaign_id, user.tenant_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    return campaign.model_dump()


@router.post("")
async def api_create_campaign(config: CampaignModel, user: UserContext = Depends(get_current_user)):
    """Create a new campaign."""
    config.tenant_id = user.tenant_id
    
    existing = await load_campaign(config.id, user.tenant_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Campaign '{config.id}' already exists")
    
    if await save_campaign(config, user.tenant_id):
        return {"status": "created", "id": config.id}
    raise HTTPException(status_code=500, detail="Failed to save campaign")


@router.put("/{campaign_id}")
async def api_update_campaign(campaign_id: str, config: CampaignModel, user: UserContext = Depends(get_current_user)):
    """Update a campaign."""
    config.id = campaign_id
    config.tenant_id = user.tenant_id
    
    # Ensure exists
    existing = await load_campaign(campaign_id, user.tenant_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if await save_campaign(config, user.tenant_id):
        return {"status": "updated", "id": campaign_id}
    raise HTTPException(status_code=500, detail="Failed to update campaign")


@router.delete("/{campaign_id}")
async def api_delete_campaign(campaign_id: str, user: UserContext = Depends(get_current_user)):
    """Delete a campaign."""
    if await delete_campaign(campaign_id, user.tenant_id):
        return {"status": "deleted", "id": campaign_id}
    raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")


@router.post("/{campaign_id}/upload-contacts")
async def api_upload_contacts(campaign_id: str, file: UploadFile = FastAPIFile(...), user: UserContext = Depends(get_current_user)):
    """Upload a CSV file of contacts. Expected columns: phone, name (+ optional extras)."""
    campaign = await load_campaign(campaign_id, user.tenant_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    contacts = []
    for row in reader:
        phone = row.get("phone", "").strip()
        if not phone:
            continue
        # Normalize phone to E.164
        if not phone.startswith("+"):
            phone = f"+{phone}"
        if not _E164_RE.match(phone):
            logger.warning(f"Skipping invalid phone in CSV: {phone}")
            continue
        name = row.get("name", "").strip()
        extra = {k: v for k, v in row.items() if k not in ("phone", "name")}
        contacts.append(ContactRecord(phone=phone, name=name, extra=extra))

    campaign.contacts = contacts
    campaign.total_contacts = len(contacts)
    campaign.called = 0
    campaign.booked = 0
    campaign.failed = 0
    
    await save_campaign(campaign, user.tenant_id)

    return {"status": "uploaded", "total_contacts": len(contacts)}


@router.post("/{campaign_id}/start")
async def api_start_campaign(campaign_id: str, user: UserContext = Depends(get_current_user)):
    campaign = await load_campaign(campaign_id, user.tenant_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    if not campaign.contacts:
        raise HTTPException(status_code=400, detail="No contacts to dial")

    # Check agent exists
    agent = await load_agent(campaign.agent_id, user.tenant_id)
    if not agent:
        raise HTTPException(status_code=400, detail=f"Agent '{campaign.agent_id}' not found")

    max_concurrent = (campaign.schedule or {}).get("max_concurrent", 3)
    dialer = CampaignDialer(campaign_id, user.tenant_id, max_concurrent=max_concurrent)
    await dialer.start()

    return {"status": "started", "campaign_id": campaign_id, "total_contacts": campaign.total_contacts}


@router.post("/{campaign_id}/pause")
async def api_pause_campaign(campaign_id: str, user: UserContext = Depends(get_current_user)):
    dialer = get_active_dialer(campaign_id)
    if not dialer:
        raise HTTPException(status_code=400, detail="Campaign is not actively dialing")
    await dialer.pause()
    return {"status": "paused", "campaign_id": campaign_id}


@router.post("/{campaign_id}/resume")
async def api_resume_campaign(campaign_id: str, user: UserContext = Depends(get_current_user)):
    dialer = get_active_dialer(campaign_id)
    if not dialer:
        raise HTTPException(status_code=400, detail="Campaign is not actively dialing")
    await dialer.resume()
    return {"status": "resumed", "campaign_id": campaign_id}


@router.post("/{campaign_id}/reset")
async def api_reset_campaign(campaign_id: str, user: UserContext = Depends(get_current_user)):
    """Reset a completed/paused campaign back to draft with all contacts pending."""
    campaign = await load_campaign(campaign_id, user.tenant_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    campaign.status = "draft"
    campaign.called = 0
    campaign.booked = 0
    campaign.failed = 0
    for contact in campaign.contacts:
        contact.status = "pending"
        contact.call_sid = None
        contact.outcome = None
    
    await save_campaign(campaign, user.tenant_id)
    return {"status": "reset", "campaign_id": campaign_id}


@router.get("/{campaign_id}/progress")
async def api_campaign_progress(campaign_id: str, user: UserContext = Depends(get_current_user)):
    campaign = await load_campaign(campaign_id, user.tenant_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    return {
        "campaign_id": campaign_id,
        "status": campaign.status,
        "total_contacts": campaign.total_contacts,
        "called": campaign.called,
        "booked": campaign.booked,
        "failed": campaign.failed,
        "remaining": campaign.total_contacts - campaign.called - campaign.failed,
    }
