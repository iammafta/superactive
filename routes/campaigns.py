"""
Superactive — Campaign Routes
"""

import csv
import io
import re

from fastapi import APIRouter, HTTPException, UploadFile, File as FastAPIFile
from loguru import logger

from agent_config import load_agent
from campaign_config import (
    CampaignConfig as CampaignModel,
    ContactRecord,
    load_campaign, save_campaign, list_campaigns, delete_campaign as delete_campaign_file,
)
from campaign_dialer import CampaignDialer, get_active_dialer

router = APIRouter(prefix="/api", tags=["campaigns"])

_E164_RE = re.compile(r'^\+[1-9]\d{1,14}$')


@router.get("/campaigns")
async def api_list_campaigns():
    return [c.model_dump() for c in list_campaigns()]


@router.get("/campaigns/{campaign_id}")
async def api_get_campaign(campaign_id: str):
    campaign = load_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    return campaign.model_dump()


@router.post("/campaigns")
async def api_create_campaign(config: CampaignModel):
    existing = load_campaign(config.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Campaign '{config.id}' already exists")
    if save_campaign(config):
        return {"status": "created", "id": config.id}
    raise HTTPException(status_code=500, detail="Failed to save campaign")


@router.put("/campaigns/{campaign_id}")
async def api_update_campaign(campaign_id: str, config: CampaignModel):
    config.id = campaign_id
    if save_campaign(config):
        return {"status": "updated", "id": campaign_id}
    raise HTTPException(status_code=500, detail="Failed to update campaign")


@router.delete("/campaigns/{campaign_id}")
async def api_delete_campaign(campaign_id: str):
    if delete_campaign_file(campaign_id):
        return {"status": "deleted", "id": campaign_id}
    raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")


@router.post("/campaigns/{campaign_id}/upload-contacts")
async def api_upload_contacts(campaign_id: str, file: UploadFile = FastAPIFile(...)):
    """Upload a CSV file of contacts. Expected columns: phone, name (+ optional extras)."""
    campaign = load_campaign(campaign_id)
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
    save_campaign(campaign)

    return {"status": "uploaded", "total_contacts": len(contacts)}


@router.post("/campaigns/{campaign_id}/start")
async def api_start_campaign(campaign_id: str):
    campaign = load_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    if not campaign.contacts:
        raise HTTPException(status_code=400, detail="No contacts to dial")

    # Check agent exists
    agent = load_agent(campaign.agent_id)
    if not agent:
        raise HTTPException(status_code=400, detail=f"Agent '{campaign.agent_id}' not found")

    max_concurrent = (campaign.schedule or {}).get("max_concurrent", 3)
    dialer = CampaignDialer(campaign_id, max_concurrent=max_concurrent)
    dialer.start()

    return {"status": "started", "campaign_id": campaign_id, "total_contacts": campaign.total_contacts}


@router.post("/campaigns/{campaign_id}/pause")
async def api_pause_campaign(campaign_id: str):
    dialer = get_active_dialer(campaign_id)
    if not dialer:
        raise HTTPException(status_code=400, detail="Campaign is not actively dialing")
    dialer.pause()
    return {"status": "paused", "campaign_id": campaign_id}


@router.post("/campaigns/{campaign_id}/resume")
async def api_resume_campaign(campaign_id: str):
    dialer = get_active_dialer(campaign_id)
    if not dialer:
        raise HTTPException(status_code=400, detail="Campaign is not actively dialing")
    dialer.resume()
    return {"status": "resumed", "campaign_id": campaign_id}


@router.post("/campaigns/{campaign_id}/reset")
async def api_reset_campaign(campaign_id: str):
    """Reset a completed/paused campaign back to draft with all contacts pending."""
    campaign = load_campaign(campaign_id)
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
    save_campaign(campaign)
    return {"status": "reset", "campaign_id": campaign_id}


@router.get("/campaigns/{campaign_id}/progress")
async def api_campaign_progress(campaign_id: str):
    campaign = load_campaign(campaign_id)
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
