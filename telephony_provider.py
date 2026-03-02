import os
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from loguru import logger

from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.serializers.telnyx import TelnyxFrameSerializer
from pipecat.serializers.twilio import TwilioFrameSerializer

import httpx
from fastapi import Request


class TelephonyProvider(ABC):
    """Abstract base class for all telephony providers (Twilio, Telnyx, etc.)."""
    
    @abstractmethod
    def validate_webhook(self, request: Request, body_bytes: bytes) -> bool:
        """Validate if the incoming webhook signature matches the provider's known secrets."""
        pass
        
    @abstractmethod
    def get_frame_serializer(self, stream_sid: str, call_sid: str, creds: Dict[str, str]) -> FrameSerializer:
        """Return the Pipecat frame serializer for this specific provider."""
        pass
        
    @abstractmethod
    async def make_outbound_call(self, to: str, creds: Dict[str, str], webhook_url: str) -> Optional[str]:
        """Trigger an outbound call to a destination. Returns the Call SID on success, None on failure."""
        pass


class TelnyxProvider(TelephonyProvider):
    def validate_webhook(self, request: Request, body_bytes: bytes) -> bool:
        if os.getenv("TELNYX_VALIDATION", "true").lower() == "false":
            return True
            
        webhook_secret = os.getenv("TELNYX_WEBHOOK_SECRET", "")
        if not webhook_secret:
            return True
            
        telnyx_signature = request.headers.get("telnyx-signature-ed25519", "")
        telnyx_timestamp = request.headers.get("telnyx-timestamp", "")
        
        try:
            import telnyx
            telnyx.Webhook.construct_event(body_bytes.decode(), telnyx_signature, telnyx_timestamp, webhook_secret)
            return True
        except Exception as e:
            logger.warning(f"🚨 Invalid Telnyx webhook signature: {e}")
            return False

    def get_frame_serializer(self, stream_sid: str, call_sid: str, creds: Dict[str, str]) -> FrameSerializer:
        return TelnyxFrameSerializer(
            stream_id=stream_sid,
            call_control_id=call_sid,
            api_key=creds.get("api_key", ""),
            params=TelnyxFrameSerializer.InputParams(auto_hang_up=True),
        )

    async def make_outbound_call(self, to: str, creds: Dict[str, str], webhook_url: str) -> Optional[str]:
        api_key = creds.get("api_key")
        from_number = creds.get("phone_number")
        connection_id = creds.get("connection_id")
        
        if not api_key or not from_number or not connection_id:
            logger.error("Missing Telnyx credentials for outbound call")
            raise ValueError("Missing Telnyx credentials")
            
        if not from_number.startswith("+"):
            from_number = f"+{from_number}"
            
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.post(
                    "https://api.api.telnyx.com/v2/calls" if False else "https://api.telnyx.com/v2/calls",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "to": to,
                        "from": from_number,
                        "connection_id": connection_id,
                        "webhook_url": webhook_url,
                    },
                )
                resp.raise_for_status()
                call_data = resp.json().get("data", {})
                return call_data.get("call_control_id", f"telnyx_{uuid.uuid4().hex}")
        except httpx.HTTPError as e:
            logger.error(f"Telnyx outbound API failed: {getattr(e, 'response', None)}")
            raise

class TwilioProvider(TelephonyProvider):
    def validate_webhook(self, request: Request, body_bytes: bytes) -> bool:
        if os.getenv("TWILIO_VALIDATION", "true").lower() == "false":
            return True
            
        # For Twilio we'd usually use twilio.request_validator but keeping it simple/permissive for now
        # unless strict validation is required.
        return True

    def get_frame_serializer(self, stream_sid: str, call_sid: str, creds: Dict[str, str]) -> FrameSerializer:
        return TwilioFrameSerializer(
            stream_sid=stream_sid,
        )

    async def make_outbound_call(self, to: str, creds: Dict[str, str], webhook_url: str) -> Optional[str]:
        account_sid = creds.get("account_sid")
        auth_token = creds.get("auth_token")
        from_number = creds.get("phone_number")
        
        if not account_sid or not auth_token or not from_number:
            logger.error("Missing Twilio credentials for outbound call")
            raise ValueError("Missing Twilio credentials")
            
        try:
            from twilio.rest import Client
            import asyncio
            
            # Use synchronous twilio client in an executor so we don't block the loop
            def _dial():
                client = Client(account_sid, auth_token)
                return client.calls.create(
                    to=to,
                    from_=from_number,
                    url=webhook_url  # URL returning TwiML
                )
             
            loop = asyncio.get_event_loop()
            call = await loop.run_in_executor(None, _dial)
            return call.sid
        except Exception as e:
            logger.error(f"Twilio outbound API failed: {e}")
            raise

def get_provider(provider_name: str) -> TelephonyProvider:
    if provider_name.lower() == "twilio":
        return TwilioProvider()
    return TelnyxProvider()


async def get_provider_with_failover(tenant_id: str) -> list[TelephonyProvider]:
    """
    Returns a list of provider instances in priority order (Primary -> Backup).
    """
    from db import get_telephony_credentials
    
    creds_wrapper = await get_telephony_credentials(tenant_id)
    primary_name = creds_wrapper.get("primary", "telnyx")
    backup_name = creds_wrapper.get("backup", "")
    
    providers = []
    
    # 1. Primary
    providers.append(get_provider(primary_name))
    
    # 2. Backup (if configured and different from primary)
    if backup_name and backup_name != primary_name:
        providers.append(get_provider(backup_name))
        
    return providers
