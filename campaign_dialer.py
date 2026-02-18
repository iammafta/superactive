"""
Superactive — Campaign Batch Dialer

Async batch dialer for outbound campaigns. Uses asyncio.Semaphore for
rate limiting and Twilio REST API for call initiation.
"""

import asyncio
import os
from typing import Optional

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


def get_active_dialer(campaign_id: str) -> Optional["CampaignDialer"]:
    return _active_campaigns.get(campaign_id)


# ── Campaign Dialer ──────────────────────────────────────────────────

class CampaignDialer:
    """Manages batch dialing for a single campaign."""

    def __init__(self, campaign_id: str, max_concurrent: int = 3):
        self.campaign_id = campaign_id
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Start unpaused
        self._stopped = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Launch the dial loop as a background task."""
        self._stopped = False
        self._pause_event.set()
        self._task = asyncio.create_task(self._dial_loop())
        _active_campaigns[self.campaign_id] = self
        logger.info(f"📣 Campaign {self.campaign_id} dialer started (max_concurrent={self.max_concurrent})")

    def pause(self):
        """Pause dialing (current calls finish, no new ones start)."""
        self._pause_event.clear()
        campaign = load_campaign(self.campaign_id)
        if campaign:
            campaign.status = "paused"
            save_campaign(campaign)
        logger.info(f"⏸️ Campaign {self.campaign_id} paused")

    def resume(self):
        """Resume a paused campaign."""
        self._pause_event.set()
        campaign = load_campaign(self.campaign_id)
        if campaign:
            campaign.status = "active"
            save_campaign(campaign)
        logger.info(f"▶️ Campaign {self.campaign_id} resumed")

    def stop(self):
        """Stop the campaign permanently."""
        self._stopped = True
        self._pause_event.set()  # Unblock if paused so loop can exit
        _active_campaigns.pop(self.campaign_id, None)

    async def _dial_loop(self):
        """Main loop — iterate contacts, dial with rate limiting."""
        campaign = load_campaign(self.campaign_id)
        if not campaign:
            logger.error(f"Campaign {self.campaign_id} not found")
            return

        campaign.status = "active"
        save_campaign(campaign)

        for i, contact in enumerate(campaign.contacts):
            if self._stopped:
                break

            # Wait if paused
            await self._pause_event.wait()
            if self._stopped:
                break

            # Skip already-processed contacts
            if contact.status in ("completed", "failed", "calling"):
                continue

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

        # Mark campaign completed if we processed all contacts
        if not self._stopped:
            campaign = load_campaign(self.campaign_id)
            if campaign:
                campaign.status = "completed"
                save_campaign(campaign)
                logger.info(f"✅ Campaign {self.campaign_id} completed")

        _active_campaigns.pop(self.campaign_id, None)

    async def _make_call(self, campaign_id: str, contact_index: int, phone: str, agent_id: str):
        """Place a single outbound call for a campaign contact."""
        campaign = load_campaign(campaign_id)
        if not campaign:
            return

        contact = campaign.contacts[contact_index]
        contact.status = "calling"
        save_campaign(campaign)

        try:
            client = get_twilio_client()
            host = os.getenv("PUBLIC_URL", "https://localhost:8765")
            from_number = os.getenv("TWILIO_PHONE_NUMBER", "")
            if not from_number.startswith("+"):
                from_number = f"+{from_number}"

            # Run Twilio API call in thread to avoid blocking event loop
            # Pass outbound flag + contact name so the agent knows it's calling out
            from urllib.parse import quote
            contact_name = quote(contact.name or "there")
            call = await asyncio.to_thread(
                client.calls.create,
                to=phone,
                from_=from_number,
                url=f"{host}/incoming-call?agent_id={agent_id}&outbound=1&contact_name={contact_name}",
            )

            contact.call_sid = call.sid
            contact.status = "completed"
            contact.outcome = "dialed"
            campaign.called += 1
            logger.info(f"📞 Campaign {campaign_id}: Called {phone} → {call.sid}")

        except Exception as e:
            contact.status = "failed"
            contact.outcome = str(e)[:200]
            campaign.failed += 1
            logger.error(f"❌ Campaign {campaign_id}: Failed to call {phone}: {e}")

        save_campaign(campaign)
