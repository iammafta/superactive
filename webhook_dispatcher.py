import hashlib
import hmac
import json
import logging
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

async def dispatch_post_call_webhook(webhook_url: str, api_key: str, call_data: Dict[str, Any]) -> bool:
    """
    Dispatch a POST request containing call data to the tenant's configured webhook securely.
    Includes an HMAC SHA-256 signature using the tenant's API Key.
    """
    if not webhook_url or not api_key:
        return False
        
    try:
        # Create a payload string to sign
        payload_bytes = json.dumps(call_data).encode("utf-8")
        
        # Sign the payload using the tenant's API key
        signature = hmac.new(api_key.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        
        headers = {
            "Content-Type": "application/json",
            "X-Superactive-Signature": signature
        }
        
        # Fire and forget essentially, but with a short timeout so we don't hang workers
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(webhook_url, content=payload_bytes, headers=headers)
            
            if response.status_code >= 400:
                logger.warning(f"Webhook delivery failed for {webhook_url}: {response.status_code} {response.text}")
                return False
                
            logger.info(f"Successfully delivered webhook to {webhook_url}")
            return True
            
    except Exception as e:
        logger.error(f"Error dispatching webhook to {webhook_url}: {e}")
        return False
