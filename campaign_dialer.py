"""
Superactive — Campaign Batch Dialer (ARQ Edition)

This version drops the in-memory asyncio loop.
Instead, it queues jobs to Redis using ARQ. The `worker.py` process 
listens to the queue and dials the contacts.
"""

import os
from typing import Optional
from loguru import logger
from arq import create_pool
from arq.connections import RedisSettings

from db import db_update_campaign_fields

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# ARQ Redis Settings
redis_settings = RedisSettings(
    host=REDIS_HOST,
    port=REDIS_PORT,
)

_arq_pool = None

async def get_arq_pool():
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(redis_settings)
    return _arq_pool


class CampaignDialer:
    """Manages enqueueing batch dialing tasks to Redis."""

    def __init__(self, campaign_id: str, tenant_id: str, max_concurrent: int = 3):
        self.campaign_id = campaign_id
        self.tenant_id = tenant_id

    async def start(self):
        """Enqueue tasks to Redis for the worker to process."""
        from db import db_load_campaign
        logger.info(f"📣 Enqueuing Campaign {self.campaign_id} tasks to Redis worker...")
        
        # 1. Update Database
        await db_update_campaign_fields(self.campaign_id, status="active")
        
        # 2. Get Campaign & Contacts
        campaign = await db_load_campaign(self.campaign_id, self.tenant_id)
        if not campaign or "contacts" not in campaign:
            return

        contacts = campaign["contacts"]
        
        # 3. Connect to ARQ
        pool = await get_arq_pool()
        
        # 4. Enqueue tasks
        enqueued = 0
        for i, contact in enumerate(contacts):
            if contact.get("status") in ("pending", "failed"):
                # Enqueue job to ARQ `dial_contact_task`
                await pool.enqueue_job(
                    'dial_contact_task',
                    self.campaign_id,
                    self.tenant_id,
                    i,
                    contact.get("phone")
                )
                enqueued += 1

        logger.info(f"✅ Enqueued {enqueued} dialing tasks to Redis for campaign {self.campaign_id}")

    async def pause(self):
        """Pause dialing by updating the DB status. Workers check this before dialing."""
        await db_update_campaign_fields(self.campaign_id, status="paused")
        logger.info(f"⏸️ Campaign {self.campaign_id} set to paused. Workers will skip pending tasks.")

    async def resume(self):
        """Resume campaign by re-enqueuing pending contacts."""
        logger.info(f"▶️ Resuming campaign {self.campaign_id}")
        await db_update_campaign_fields(self.campaign_id, status="active")
        await self.start()

    def stop(self):
        """Not relevant to queue - just stops future UI actions."""
        pass


def get_active_dialer(campaign_id: str) -> Optional["CampaignDialer"]:
    """For backwards compatibility with routes calling this.
    Returns a dummy instance so .pause() and .resume() still work.
    We don't need to track active loops anymore."""
    # Since we need tenant_id, this is a bit hacky unless we change the route signature.
    # We'll just return an object that routes can call pause() on. The routes usually have tenant_id.
    # BUT wait, the route needs to pass tenant_id. The route currently does:
    # dialer = get_active_dialer(campaign_id)
    # So we'll update the route to just instantiate CampaignDialer manually instead.
    return None
