"""
Superactive — Campaign Batch Dialer

Async batch dialer for outbound campaigns. Uses asyncio.Semaphore for
rate limiting and Twilio REST API for call initiation.
Enforces campaign schedule (business hours) and retries failed calls.
Persisted in SQLite via db.py (through campaign_config abstraction).
"""

import asyncio
import os
import json
from datetime import datetime, time as dtime
from typing import Optional
from urllib.parse import quote

from loguru import logger

from campaign_config import load_campaign, save_campaign


# ── Shared Twilio Client (singleton) ─────────────────────────────────

_twilio_client = None


def get_twilio_client():
    """Get or create a shared Twilio client."""
    global _twilio_client
    if _twilio_client is None:
        from twilio.rest import Client
        _twilio_client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )
    return _twilio_client


# ── Active Campaign Registry ─────────────────────────────────────────

_active_campaigns: dict[str, "CampaignDialer"] = {}

# Per-campaign locks to prevent concurrent load→modify→save races
_campaign_locks: dict[str, asyncio.Lock] = {}


def _get_lock(campaign_id: str) -> asyncio.Lock:
    """Get or create an asyncio.Lock for a specific campaign."""
    if campaign_id not in _campaign_locks:
        _campaign_locks[campaign_id] = asyncio.Lock()
    return _campaign_locks[campaign_id]


def get_active_dialer(campaign_id: str) -> Optional["CampaignDialer"]:
    return _active_campaigns.get(campaign_id)


# ── Campaign Dialer ──────────────────────────────────────────────────

class CampaignDialer:
    """Manages batch dialing for a single campaign."""

    MAX_RETRIES = 1           # Retry failed calls once
    RETRY_DELAY_SECONDS = 300  # 5 minutes between retries

    def __init__(self, campaign_id: str, tenant_id: str, max_concurrent: int = 3):
        self.campaign_id = campaign_id
        self.tenant_id = tenant_id
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Start unpaused
        self._stopped = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Launch the dial loop as a background task."""
        self._stopped = False
        self._pause_event.set()
        self._task = asyncio.create_task(self._dial_loop())
        _active_campaigns[self.campaign_id] = self
        logger.info(f"📣 Campaign {self.campaign_id} dialer started (max_concurrent={self.max_concurrent})")

    async def pause(self):
        """Pause dialing (current calls finish, no new ones start)."""
        self._pause_event.clear()
        async with _get_lock(self.campaign_id):
            campaign = await load_campaign(self.campaign_id, self.tenant_id)
            if campaign:
                campaign.status = "paused"
                await save_campaign(campaign, self.tenant_id)
        logger.info(f"⏸️ Campaign {self.campaign_id} paused")

    async def resume(self):
        """Resume a paused campaign."""
        self._pause_event.set()
        async with _get_lock(self.campaign_id):
            campaign = await load_campaign(self.campaign_id, self.tenant_id)
            if campaign:
                campaign.status = "active"
                await save_campaign(campaign, self.tenant_id)
        logger.info(f"▶️ Campaign {self.campaign_id} resumed")

    def stop(self):
        """Stop the campaign permanently."""
        self._stopped = True
        self._pause_event.set()  # Unblock if paused so loop can exit
        _active_campaigns.pop(self.campaign_id, None)

    def _is_within_schedule(self, schedule: Optional[dict]) -> bool:
        """Check if current time is within the campaign's allowed calling window."""
        if not schedule:
            return True  # No schedule = always allowed

        now = datetime.now()

        # Check day of week (0=Monday, 6=Sunday)
        allowed_days = schedule.get("days_of_week")
        if allowed_days and now.strftime("%A").lower() not in [d.lower() for d in allowed_days]:
            logger.info(f"📅 Campaign {self.campaign_id}: Today ({now.strftime('%A')}) not in schedule {allowed_days}")
            return False

        # Check time window
        start_str = schedule.get("start_time", "09:00")
        end_str = schedule.get("end_time", "17:00")
        try:
            start_h, start_m = map(int, start_str.split(":"))
            end_h, end_m = map(int, end_str.split(":"))
            start = dtime(start_h, start_m)
            end = dtime(end_h, end_m)
            current = now.time()
            if not (start <= current <= end):
                logger.info(f"⏰ Campaign {self.campaign_id}: Current time {current.strftime('%H:%M')} outside window {start_str}-{end_str}")
                return False
        except (ValueError, TypeError):
            pass  # Malformed schedule — allow calling

        return True

    async def _wait_for_schedule(self, schedule: Optional[dict]):
        """Sleep until we're within the campaign schedule window. Checks every 60s."""
        while not self._stopped and not self._is_within_schedule(schedule):
            logger.info(f"💤 Campaign {self.campaign_id}: Outside business hours, checking again in 60s")
            for _ in range(60):
                if self._stopped:
                    return
                await asyncio.sleep(1.0)

    async def _dial_loop(self):
        """Main loop — iterate contacts, dial with rate limiting."""
        async with _get_lock(self.campaign_id):
            campaign = await load_campaign(self.campaign_id, self.tenant_id)
            if not campaign:
                logger.error(f"Campaign {self.campaign_id} not found")
                return
            campaign.status = "active"
            await save_campaign(campaign, self.tenant_id)

        schedule = campaign.schedule
        failed_contacts = []  # Track for retry pass

        for i, contact in enumerate(campaign.contacts):
            if self._stopped:
                break

            # Wait if paused
            await self._pause_event.wait()
            if self._stopped:
                break

            # Skip already-processed contacts
            if contact.status in ("completed", "calling"):
                continue
            # Collect previously failed for retry, but skip in first pass
            if contact.status == "failed":
                failed_contacts.append(i)
                continue

            # Enforce business hours
            await self._wait_for_schedule(schedule)
            if self._stopped:
                break

            # Rate limit via semaphore
            async with self._semaphore:
                if self._stopped:
                    break
                await self._make_call(campaign.id, i, contact.phone, campaign.agent_id)

            # Wait between calls — gives the current call time to complete
            # before dialing the next contact (especially important when
            # testing with the same phone number for all contacts)
            logger.info(f"⏳ Campaign {self.campaign_id}: Waiting 30s before next call...")
            for _ in range(30):
                if self._stopped:
                    break
                await asyncio.sleep(1.0)

        # --- Retry pass: re-attempt failed contacts once ---
        if not self._stopped and self.MAX_RETRIES > 0:
            # Reload campaign to pick up any newly failed contacts from this pass
            async with _get_lock(self.campaign_id):
                campaign = await load_campaign(self.campaign_id, self.tenant_id)
            
            if campaign:
                retry_indices = [i for i, c in enumerate(campaign.contacts) if c.status == "failed"]
                if retry_indices:
                    logger.info(f"🔄 Campaign {self.campaign_id}: Retrying {len(retry_indices)} failed contacts in {self.RETRY_DELAY_SECONDS}s")
                    for _ in range(self.RETRY_DELAY_SECONDS):
                        if self._stopped:
                            break
                        await asyncio.sleep(1.0)

                    for i in retry_indices:
                        if self._stopped:
                            break
                        await self._pause_event.wait()
                        if self._stopped:
                            break

                        # Reset status to pending for retry
                        async with _get_lock(self.campaign_id):
                            campaign = await load_campaign(self.campaign_id, self.tenant_id)
                            if campaign:
                                campaign.contacts[i].status = "pending"
                                campaign.failed = max(0, campaign.failed - 1)
                                await save_campaign(campaign, self.tenant_id)

                        await self._wait_for_schedule(schedule)
                        if self._stopped:
                            break

                        async with self._semaphore:
                            if self._stopped:
                                break
                            contact = campaign.contacts[i]
                            await self._make_call(campaign.id, i, contact.phone, campaign.agent_id)

                        for _ in range(30):
                            if self._stopped:
                                break
                            await asyncio.sleep(1.0)

        # Mark campaign completed if we processed all contacts
        if not self._stopped:
            async with _get_lock(self.campaign_id):
                campaign = await load_campaign(self.campaign_id, self.tenant_id)
                if campaign:
                    campaign.status = "completed"
                    await save_campaign(campaign, self.tenant_id)
                    logger.info(f"✅ Campaign {self.campaign_id} completed")

        _active_campaigns.pop(self.campaign_id, None)

    async def _make_call(self, campaign_id: str, contact_index: int, phone: str, agent_id: str):
        """Place a single outbound call for a campaign contact."""
        # Mark contact as "calling" under lock
        async with _get_lock(campaign_id):
            campaign = await load_campaign(campaign_id, self.tenant_id)
            if not campaign:
                return
            contact = campaign.contacts[contact_index]
            contact.status = "calling"
            await save_campaign(campaign, self.tenant_id)

        # Twilio API call happens outside the lock (it's slow/network I/O)
        try:
            client = get_twilio_client()
            host = os.getenv("PUBLIC_URL", "https://localhost:8765")
            from_number = os.getenv("TWILIO_PHONE_NUMBER", "")
            if not from_number.startswith("+"):
                from_number = f"+{from_number}"

            contact_name = quote(contact.name or "there")
            # Pass extra campaign data (e.g. last_visit, doctor) so the agent
            # knows WHY it's calling this specific person
            url = f"{host}/incoming-call?agent_id={agent_id}&outbound=1&contact_name={contact_name}"
            extra = {k: v for k, v in contact.model_dump().items()
                     if k not in ("phone", "name", "status", "call_sid", "outcome")}
            if extra.get("extra"):
                url += f"&contact_extra={quote(json.dumps(extra['extra']))}"
            
            # Use asyncio.to_thread for the blocking Twilio client call
            call = await asyncio.to_thread(
                client.calls.create,
                to=phone,
                from_=from_number,
                url=url,
            )
            call_sid = call.sid
            outcome = "dialed"
            success = True
            logger.info(f"📞 Campaign {campaign_id}: Called {phone} → {call_sid}")

        except Exception as e:
            call_sid = None
            outcome = str(e)[:200]
            success = False
            logger.error(f"❌ Campaign {campaign_id}: Failed to call {phone}: {e}")

        # Update contact result under lock
        async with _get_lock(campaign_id):
            campaign = await load_campaign(campaign_id, self.tenant_id)
            if not campaign:
                return
            contact = campaign.contacts[contact_index]
            if success:
                contact.call_sid = call_sid
                contact.status = "completed"
                contact.outcome = outcome
                campaign.called += 1
            else:
                contact.status = "failed"
                contact.outcome = outcome
                campaign.failed += 1
            await save_campaign(campaign, self.tenant_id)
