"""
Superactive — Worker Process (ARQ)

This worker consumes tasks from Redis (e.g., dial_contact) to ensure
campaign dialing is durable and survives API server restarts.
"""

import asyncio
import os
import ssl
from datetime import datetime
from loguru import logger
from arq import Worker
from arq.connections import RedisSettings

from telemetry import init_telemetry
init_telemetry("superactive-worker")

# Import your database and telephony logic
from db import (
    init_db, get_pool,
    db_load_agent, db_load_campaign, db_update_contact_by_index, db_get_tenant,
    get_telephony_credentials,
)
from telephony_provider import get_provider
# Note: In a full refactor, we would extract the dial logic from CampaignDialer into here.
# For now, we stub the worker task to show how it plugs in.

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# ARQ Redis Settings
redis_settings = RedisSettings(
    host=REDIS_HOST,
    port=REDIS_PORT,
)


async def startup(ctx):
    """Run on worker startup."""
    logger.info("🚀 ARQ Worker starting up...")
    await init_db()
    logger.info("✅ Worker connected to Database")


async def shutdown(ctx):
    """Run on worker shutdown."""
    logger.info("🛑 ARQ Worker shutting down...")
    pool = await get_pool()
    if pool:
        await pool.close()


async def dial_contact_task(ctx, campaign_id: str, tenant_id: str, contact_index: int, phone: str):
    """
    Task picked up by the worker to dial a single contact via Telnyx.
    """
    logger.info(f"📞 Task processing: dial_contact (campaign={campaign_id}, index={contact_index}, phone={phone})")
    
    # 1. Load context
    campaign = await db_load_campaign(campaign_id, tenant_id)
    if not campaign or campaign["status"] != "active":
        logger.warning(f"Campaign {campaign_id} is not active. Canceling dial task.")
        return False
        
    tenant = await db_get_tenant(tenant_id)
    agent = await db_load_agent(campaign["agent_id"], tenant_id)
    
    if not tenant or not agent:
        logger.error("Missing tenant or agent data")
        return False
        
    # 2. Mark contact as dialing
    await db_update_contact_by_index(campaign_id, contact_index, status="dialing")
    # 3. Perform Dial via TelephonyProvider
    try:
        creds_wrapper = await get_telephony_credentials(tenant_id)
        host = os.getenv("PUBLIC_URL", "")
        agent_id = campaign["agent_id"]
        
        provider_name = creds_wrapper.get("provider", "telnyx")
        backup_name = creds_wrapper.get("backup_provider", "")
        
        provider = get_provider(provider_name)
        creds = creds_wrapper.get(provider_name, {})
        webhook_url = f"{host}/incoming-call/{provider_name}?agent_id={agent_id}&outbound=1"
        
        call_sid = None
        try:
            call_sid = await provider.make_outbound_call(phone, creds, webhook_url)
        except Exception as e:
            logger.error(f"Worker primary provider ({provider_name}) failed: {e}")
            if backup_name:
                logger.warning(f"🔄 Worker failing over to backup provider: {backup_name}")
                backup_provider = get_provider(backup_name)
                backup_creds = creds_wrapper.get(backup_name, {})
                backup_webhook = f"{host}/incoming-call/{backup_name}?agent_id={agent_id}&outbound=1"
                call_sid = await backup_provider.make_outbound_call(phone, backup_creds, backup_webhook)
                
        if not call_sid:
            raise Exception("All telephony providers failed")

        # 4. Mark success / save SID
        await db_update_contact_by_index(campaign_id, contact_index, status="called", call_sid=call_sid)
        logger.info(f"✅ Call initiated successfully. SID: {call_sid}")
        return True

    except Exception as e:
        logger.error(f"❌ Dial failed for {phone}: {e}")
        await db_update_contact_by_index(campaign_id, contact_index, status="failed")
        return False


# Worker Configuration
class WorkerSettings:
    functions = [dial_contact_task]
    redis_settings = redis_settings
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 100  # Concurrency limit
    max_tries = 3   # Retry policy
    job_timeout = 60 # 1 minute max per dial task

if __name__ == "__main__":
    logger.info("Execute this worker via: arq worker.WorkerSettings")
