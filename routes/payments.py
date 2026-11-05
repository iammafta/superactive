"""Stripe webhook. This route is public and is checked with the Stripe signature."""

import os

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from orders import apply_checkout_completed

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    signature = request.headers.get("stripe-signature", "")
    payload = await request.body()
    if not secret or not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    try:
        import stripe

        event = stripe.Webhook.construct_event(payload, signature, secret)
    except Exception as exc:
        logger.warning(f"Stripe signature rejected: {exc}")
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    if event["type"] == "checkout.session.completed":
        outcome = await apply_checkout_completed(event["data"]["object"])
        return {"ok": True, "outcome": outcome}
    return {"ok": True, "outcome": "ignored"}
