"""
Superactive — Campaign Configuration System

Pydantic models for batch outbound calling campaigns.
Each campaign links to an agent config and contains a list of contacts to dial.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from loguru import logger


CAMPAIGNS_DIR = Path(__file__).parent / "data" / "campaigns"


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


# ── CRUD Operations ──────────────────────────────────────────────────

def _ensure_dir():
    CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)


def load_campaign(campaign_id: str) -> Optional[CampaignConfig]:
    path = CAMPAIGNS_DIR / f"{campaign_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return CampaignConfig(**data)
    except Exception as e:
        logger.error(f"Failed to load campaign {campaign_id}: {e}")
        return None


def save_campaign(config: CampaignConfig) -> bool:
    _ensure_dir()
    config.updated_at = datetime.now().isoformat()
    path = CAMPAIGNS_DIR / f"{config.id}.json"
    try:
        path.write_text(config.model_dump_json(indent=2))
        return True
    except Exception as e:
        logger.error(f"Failed to save campaign {config.id}: {e}")
        return False


def list_campaigns() -> list[CampaignConfig]:
    _ensure_dir()
    campaigns = []
    for path in sorted(CAMPAIGNS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text())
            campaigns.append(CampaignConfig(**data))
        except Exception as e:
            logger.error(f"Failed to load {path.name}: {e}")
    return campaigns


def delete_campaign(campaign_id: str) -> bool:
    path = CAMPAIGNS_DIR / f"{campaign_id}.json"
    if path.exists():
        path.unlink()
        logger.info(f"Deleted campaign: {campaign_id}")
        return True
    return False
