"""
Superactive — Campaign Configuration System

Pydantic models for batch outbound calling campaigns.
Each campaign links to an agent config and contains a list of contacts to dial.
Persisted in SQLite via db.py.
"""

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from loguru import logger

from db import (
    db_load_campaign,
    db_save_campaign,
    db_list_campaigns,
    db_delete_campaign,
    db_save_contacts,
    db_get_contacts
)


class ContactRecord(BaseModel):
    """Single contact in a campaign."""
    phone: str
    name: str = ""
    status: str = "pending"  # pending | calling | completed | failed
    call_sid: Optional[str] = None
    outcome: Optional[str] = None
    extra: dict = Field(default_factory=dict)


class CampaignConfig(BaseModel):
    """Full campaign configuration."""

    id: str
    tenant_id: str
    name: str
    agent_id: str
    status: str = "draft"  # draft | active | paused | completed
    contacts: list[ContactRecord] = Field(default_factory=list)
    total_contacts: int = 0
    called: int = 0
    booked: int = 0
    failed: int = 0
    schedule: Optional[dict] = None  # {max_concurrent, start_time, end_time, days_of_week}
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── CRUD Operations (Async + DB) ─────────────────────────────────────

async def load_campaign(campaign_id: str, tenant_id: str = None) -> Optional[CampaignConfig]:
    """Load a campaign from DB."""
    data = await db_load_campaign(campaign_id, tenant_id)
    if not data:
        return None
    try:
        # Load contacts separately if needed (db_load_campaign already does this but let's be sure)
        # Actually db_load_campaign returns contacts list in the dict
        return CampaignConfig(**data)
    except Exception as e:
        logger.error(f"Failed to parse campaign {campaign_id}: {e}")
        return None


async def save_campaign(config: CampaignConfig, tenant_id: str) -> bool:
    """Save a campaign to DB."""
    if config.tenant_id != tenant_id:
        logger.error(f"Tenant mismatch: {config.tenant_id} != {tenant_id}")
        return False

    # Save campaign metadata
    success = await db_save_campaign(config.model_dump(), tenant_id)
    if not success:
        return False

    # Save contacts
    contacts_data = [c.model_dump() for c in config.contacts]
    await db_save_contacts(config.id, contacts_data)
    
    return True


async def list_campaigns(tenant_id: str) -> list[CampaignConfig]:
    """List all campaigns for a tenant."""
    rows = await db_list_campaigns(tenant_id)
    campaigns = []
    for row in rows:
        try:
            # List view might not need full contacts, but model requires valid list
            # db_list_campaigns returns basic info
            campaigns.append(CampaignConfig(**row))
        except Exception as e:
            logger.error(f"Skipping invalid campaign: {e}")
    return campaigns


async def delete_campaign(campaign_id: str, tenant_id: str) -> bool:
    """Delete a campaign."""
    return await db_delete_campaign(campaign_id, tenant_id)
