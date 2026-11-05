"""Restaurant menu, pickup windows, and takeout orders.

Prices and times returned here are the only ones the voice agent may speak.
The voice handlers never mark an order paid.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from db import get_db

LEGACY_PROMPT_MARKER = "Popular dishes: our signature pasta"
HOLD_MINUTES = 15

DEMO_ITEMS = (
    {
        "id": "signature-pasta",
        "name": "Signature Pasta",
        "description": "House pasta with the evening sauce.",
        "price_cents": 1800,
        "available": 1,
    },
    {
        "id": "grilled-salmon",
        "name": "Grilled Salmon",
        "description": "Salmon with a lemon glaze.",
        "price_cents": 2400,
        "available": 1,
    },
    {
        "id": "chefs-tasting",
        "name": "Chef's Tasting Menu",
        "description": "A longer tasting. It is off the board tonight.",
        "price_cents": 6500,
        "available": 0,
    },
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_slot_label(moment: datetime) -> str:
    hour = moment.hour % 12 or 12
    suffix = "AM" if moment.hour < 12 else "PM"
    return f"{hour}:{moment.minute:02d} {suffix}"


def dollars(cents: int) -> str:
    return f"${cents / 100:.2f}"


def _row(row) -> dict:
    return dict(row) if row is not None else {}


async def expire_holds(tenant_id: str, now: Optional[datetime] = None) -> None:
    """Mark unpaid holds past their expiry so the pickup slot opens again."""
    moment = format_stamp(now or utc_now())
    db = await get_db()
    try:
        await db.execute(
            """
            UPDATE orders
            SET status = 'expired'
            WHERE tenant_id = ?
              AND status IN ('draft', 'link_sent')
              AND expires_at IS NOT NULL
              AND expires_at < ?
            """,
            (tenant_id, moment),
        )
        await db.commit()
    finally:
        await db.close()


async def list_menu(tenant_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT id, name, description, price_cents, available, choice_name, choice_options
            FROM menu_items
            WHERE tenant_id = ?
            ORDER BY name
            """,
            (tenant_id,),
        )
        items = []
        for row in await cursor.fetchall():
            item = _row(row)
            raw = item.get("choice_options") or "[]"
            item["choice_options"] = json.loads(raw) if isinstance(raw, str) else raw
            item["available"] = bool(item["available"])
            items.append(item)
        return items
    finally:
        await db.close()


async def create_menu_item(tenant_id: str, fields: dict) -> dict:
    item_id = fields.get("id") or str(uuid.uuid4())
    choice_options = fields.get("choice_options") or []
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO menu_items
                (id, tenant_id, name, description, price_cents, available, choice_name, choice_options)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                tenant_id,
                fields["name"].strip(),
                (fields.get("description") or "").strip(),
                int(fields["price_cents"]),
                1 if fields.get("available", True) else 0,
                fields.get("choice_name"),
                json.dumps(choice_options),
            ),
        )
        await db.commit()
    finally:
        await db.close()
    found = await _get_menu_item(tenant_id, item_id)
    return found or {}


async def update_menu_item(tenant_id: str, item_id: str, fields: dict) -> Optional[dict]:
    current = await _get_menu_item(tenant_id, item_id)
    if not current:
        return None
    name = fields.get("name", current["name"])
    description = fields.get("description", current["description"])
    price_cents = int(fields.get("price_cents", current["price_cents"]))
    if "available" in fields:
        available = 1 if fields["available"] else 0
    else:
        available = 1 if current["available"] else 0
    choice_name = fields.get("choice_name", current.get("choice_name"))
    choice_options = fields.get("choice_options", current.get("choice_options") or [])
    db = await get_db()
    try:
        await db.execute(
            """
            UPDATE menu_items
            SET name = ?, description = ?, price_cents = ?, available = ?,
                choice_name = ?, choice_options = ?
            WHERE tenant_id = ? AND id = ?
            """,
            (
                str(name).strip(),
                (description or "").strip(),
                price_cents,
                available,
                choice_name,
                json.dumps(choice_options),
                tenant_id,
                item_id,
            ),
        )
        await db.commit()
    finally:
        await db.close()
    return await _get_menu_item(tenant_id, item_id)


async def _get_menu_item(tenant_id: str, item_id: str) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT id, name, description, price_cents, available, choice_name, choice_options
            FROM menu_items
            WHERE tenant_id = ? AND id = ?
            """,
            (tenant_id, item_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        item = _row(row)
        raw = item.get("choice_options") or "[]"
        item["choice_options"] = json.loads(raw) if isinstance(raw, str) else raw
        item["available"] = bool(item["available"])
        return item
    finally:
        await db.close()


def _match_item(items: list[dict], query: str) -> Optional[dict]:
    needle = (query or "").casefold().strip()
    if not needle:
        return None
    exact = [item for item in items if item["name"].casefold() == needle]
    if len(exact) == 1:
        return exact[0]
    partial = [
        item
        for item in items
        if needle in item["name"].casefold() or item["name"].casefold() in needle
    ]
    if len(partial) == 1:
        return partial[0]
    return None


def _available_names(items: list[dict], skip: Optional[str] = None) -> list[str]:
    names = []
    for item in items:
        if item["available"] and item["name"] != skip:
            names.append(item["name"])
    return names[:3]


async def get_item(tenant_id: str, name: str) -> dict:
    items = await list_menu(tenant_id)
    match = _match_item(items, name)
    if not match:
        return {
            "found": False,
            "alternatives": _available_names(items),
            "message": "That dish is not on the menu. Offer only the alternative names.",
        }
    payload = {
        "found": True,
        "name": match["name"],
        "description": match["description"],
        "price_cents": match["price_cents"],
        "available": match["available"],
        "choice_name": match.get("choice_name"),
        "choice_options": match.get("choice_options") or [],
        "alternatives": _available_names(items, skip=match["name"]),
    }
    if match["available"]:
        payload["message"] = (
            f"{match['name']} is {dollars(match['price_cents'])}. Speak this price only."
        )
    else:
        payload["message"] = (
            f"{match['name']} is off the menu. Offer only the alternative names."
        )
    return payload


def _quantity(raw) -> Optional[int]:
    try:
        qty = int(raw)
    except (TypeError, ValueError):
        return None
    if qty < 1:
        return None
    return qty


async def price_order(tenant_id: str, items: list[dict]) -> dict:
    menu = await list_menu(tenant_id)
    lines = []
    problems = []
    for requested in items or []:
        name = (requested.get("name") or "").strip()
        qty = _quantity(requested.get("qty", requested.get("quantity", 1)))
        match = _match_item(menu, name)
        if qty is None:
            problems.append({"name": name or "item", "reason": "Quantity must be at least 1."})
            continue
        if not match:
            problems.append({"name": name or "item", "reason": "Not on the menu."})
            continue
        if not match["available"]:
            problems.append({"name": match["name"], "reason": "Unavailable."})
            continue
        lines.append(
            {
                "name": match["name"],
                "item_id": match["id"],
                "quantity": qty,
                "unit_price_cents": match["price_cents"],
                "line_cents": match["price_cents"] * qty,
            }
        )
    if problems or not lines:
        return {
            "ok": False,
            "unavailable": problems,
            "alternatives": _available_names(menu),
            "message": "Do not read a total. Offer only dishes that are still on the menu.",
        }
    total = sum(line["line_cents"] for line in lines)
    return {
        "ok": True,
        "lines": lines,
        "total_cents": total,
        "message": f"The total is {dollars(total)}. Read this total. Do not add it yourself.",
    }


def parse_service_day(value: Optional[str], today: Optional[datetime] = None) -> datetime:
    base = today or utc_now()
    text = (value or "").strip()
    if not text or text.casefold() == "today":
        return base
    if text.casefold() == "tomorrow":
        return base + timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return base


def _slot_moments(day: datetime, open_time: str, close_time: str, slot_minutes: int) -> list[datetime]:
    open_hour, open_minute = [int(part) for part in open_time.split(":")]
    close_hour, close_minute = [int(part) for part in close_time.split(":")]
    start = day.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
    end = day.replace(hour=close_hour, minute=close_minute, second=0, microsecond=0)
    if end <= start:
        return []
    cursor = start
    slots = []
    while cursor < end:
        slots.append(cursor)
        cursor += timedelta(minutes=max(slot_minutes, 1))
    return slots


def slot_key(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M")


async def list_hours(tenant_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT id, weekday, open_time, close_time, slot_minutes, capacity
            FROM hours
            WHERE tenant_id = ?
            ORDER BY weekday
            """,
            (tenant_id,),
        )
        return [_row(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def replace_hours(tenant_id: str, rows: list[dict]) -> list[dict]:
    db = await get_db()
    try:
        await db.execute("DELETE FROM hours WHERE tenant_id = ?", (tenant_id,))
        for row in rows:
            weekday = int(row["weekday"])
            await db.execute(
                """
                INSERT INTO hours
                    (id, tenant_id, weekday, open_time, close_time, slot_minutes, capacity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{tenant_id}-{weekday}",
                    tenant_id,
                    weekday,
                    row["open_time"],
                    row["close_time"],
                    int(row.get("slot_minutes") or 15),
                    int(row.get("capacity") or 1),
                ),
            )
        await db.commit()
    finally:
        await db.close()
    return await list_hours(tenant_id)


async def _occupied(tenant_id: str, pickup_key: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT COUNT(*) FROM orders
            WHERE tenant_id = ?
              AND pickup_at = ?
              AND status IN ('draft', 'link_sent', 'paid')
            """,
            (tenant_id, pickup_key),
        )
        return (await cursor.fetchone())[0]
    finally:
        await db.close()


async def pickup_windows(tenant_id: str, day_text: Optional[str] = None) -> dict:
    await expire_holds(tenant_id)
    day = parse_service_day(day_text)
    weekday = day.weekday()
    hours = [row for row in await list_hours(tenant_id) if int(row["weekday"]) == weekday]
    open_slots = []
    for row in hours:
        capacity = int(row["capacity"] or 1)
        for moment in _slot_moments(
            day,
            row["open_time"],
            row["close_time"],
            int(row["slot_minutes"] or 15),
        ):
            key = slot_key(moment)
            if await _occupied(tenant_id, key) < capacity:
                open_slots.append(
                    {
                        "label": format_slot_label(moment),
                        "pickup_at": key,
                        "capacity": capacity,
                    }
                )
    open_slots = open_slots[:3]
    if not open_slots:
        return {
            "available": False,
            "date": day.strftime("%Y-%m-%d"),
            "slots": [],
            "message": "No pickup times are open. Do not offer a time.",
        }
    labels = [slot["label"] for slot in open_slots]
    return {
        "available": True,
        "date": day.strftime("%Y-%m-%d"),
        "slots": labels,
        "slot_keys": {
            slot["label"]: {"pickup_at": slot["pickup_at"], "capacity": slot["capacity"]}
            for slot in open_slots
        },
        "message": f"Open times are {', '.join(labels)}. Offer only these times.",
    }


async def _resolve_window(tenant_id: str, day_text: Optional[str], pickup_time: str) -> Optional[dict]:
    windows = await pickup_windows(tenant_id, day_text)
    keys = windows.get("slot_keys") or {}
    needle = (pickup_time or "").strip()
    for label, info in keys.items():
        if info["pickup_at"] == needle or label.casefold() == needle.casefold():
            return {"label": label, **info}
    return None


async def hold_order(
    tenant_id: str,
    items: list[dict],
    pickup_time: str,
    name: str = "",
    phone: str = "",
    agent_id: str = "",
    call_id: Optional[str] = None,
    day_text: Optional[str] = None,
) -> dict:
    quoted = await price_order(tenant_id, items)
    if not quoted.get("ok"):
        return quoted
    chosen = await _resolve_window(tenant_id, day_text, pickup_time)
    if not chosen or await _occupied(tenant_id, chosen["pickup_at"]) >= chosen["capacity"]:
        windows = await pickup_windows(tenant_id, day_text)
        return {
            "ok": False,
            "status": "window_unavailable",
            "slots": windows.get("slots") or [],
            "message": "That time is not open. Offer only the returned times.",
        }
    order_id = "ord_" + uuid.uuid4().hex[:8]
    expires = format_stamp(utc_now() + timedelta(minutes=HOLD_MINUTES))
    total = quoted["total_cents"]
    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO orders (
                id, tenant_id, agent_id, call_id, status, total_cents, pickup_at,
                expires_at, customer_name, customer_phone
            ) VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                tenant_id,
                agent_id,
                call_id,
                total,
                chosen["pickup_at"],
                expires,
                name or "",
                phone or "",
            ),
        )
        for line in quoted["lines"]:
            await db.execute(
                """
                INSERT INTO order_items
                    (order_id, tenant_id, item_id, name, quantity, unit_price_cents)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    tenant_id,
                    line["item_id"],
                    line["name"],
                    line["quantity"],
                    line["unit_price_cents"],
                ),
            )
        await db.commit()
    finally:
        await db.close()
    return {
        "ok": True,
        "status": "draft",
        "order_id": order_id,
        "total_cents": total,
        "pickup_time": chosen["label"],
        "pickup_at": chosen["pickup_at"],
        "expires_at": expires,
        "message": (
            f"The order is held, not placed, until {expires}. "
            f"The total is {dollars(total)} at {chosen['label']}."
        ),
    }


async def get_order(tenant_id: str, order_id: str) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM orders WHERE tenant_id = ? AND id = ?",
            (tenant_id, order_id),
        )
        row = await cursor.fetchone()
        return _row(row) if row else None
    finally:
        await db.close()


def send_sms(phone: str, body: str) -> dict:
    """Send one Twilio SMS. A missing credential is a failure, not a queued send."""
    account = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_PHONE_NUMBER", "")
    if not account or not token or not from_number or not phone:
        logger.error("SMS failed: Twilio is not configured")
        return {"status": "failed", "message": "The text could not be sent."}
    try:
        from twilio.rest import Client

        message = Client(account, token).messages.create(
            body=body,
            from_=from_number,
            to=phone,
        )
        return {"status": "sent", "sid": message.sid}
    except Exception as exc:
        logger.error(f"SMS failed: {exc}")
        return {"status": "failed", "message": "The text could not be sent."}


def _payment_body(order: dict, url: str) -> str:
    return (
        f"Order {order['id']} for {dollars(order['total_cents'])} is held until {order['expires_at']}. "
        f"Pay here: {url} The kitchen starts when payment lands."
    )


async def _set_order_link(tenant_id: str, order_id: str, url: str, session_id: str, status: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            """
            UPDATE orders
            SET payment_url = ?, stripe_session_id = ?, status = ?
            WHERE tenant_id = ? AND id = ?
            """,
            (url, session_id, status, tenant_id, order_id),
        )
        await db.commit()
    finally:
        await db.close()


async def send_payment_link(tenant_id: str, order_id: str) -> dict:
    await expire_holds(tenant_id)
    order = await get_order(tenant_id, order_id)
    if not order or order["status"] != "draft":
        return {
            "ok": False,
            "status": "not_draft",
            "message": "There is no held order to pay. Do not invent a link.",
        }
    secret = os.getenv("STRIPE_SECRET_KEY", "")
    if not secret:
        return {
            "ok": False,
            "status": "unconfigured",
            "message": "Payment is not configured. Do not invent a payment link.",
        }
    import stripe

    stripe.api_key = secret
    base = os.getenv("PUBLIC_URL", "https://example.com").rstrip("/")
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(order["total_cents"]),
                        "product_data": {"name": f"Order {order_id}"},
                    },
                }
            ],
            metadata={"order_id": order_id, "tenant_id": tenant_id},
            success_url=f"{base}/paid?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}/paid?canceled=1",
        )
    except Exception as exc:
        logger.error(f"Stripe session failed: {exc}")
        return {
            "ok": False,
            "status": "stripe_error",
            "message": "The payment link could not be created. Do not invent a URL.",
        }
    url = session.url or ""
    await _set_order_link(tenant_id, order_id, url, session.id, "link_sent")
    order = await get_order(tenant_id, order_id)
    sms = send_sms(order.get("customer_phone") or "", _payment_body(order, url))
    if sms["status"] != "sent":
        await _set_order_link(tenant_id, order_id, "", "", "draft")
        return {
            "ok": False,
            "status": "sms_failed",
            "message": "The text did not send. Do not say a payment text went out.",
        }
    return {
        "ok": True,
        "status": "link_sent",
        "order_id": order_id,
        "url": url,
        "expires_at": order["expires_at"],
        "total_cents": order["total_cents"],
        "message": (
            f"A text was sent for {dollars(order['total_cents'])}. "
            "The order is held until payment lands. It is not placed."
        ),
    }


async def order_status(tenant_id: str, order_id: str) -> dict:
    await expire_holds(tenant_id)
    order = await get_order(tenant_id, order_id)
    if not order:
        return {
            "found": False,
            "status": "missing",
            "message": "That order was not found. Do not confirm it.",
        }
    status = order["status"]
    if status == "paid":
        message = (
            f"Order {order_id} is paid and placed for {order.get('pickup_at')}. "
            "You may confirm it."
        )
    else:
        message = (
            f"Order {order_id} is {status}. Do not say the order is placed. "
            "The kitchen starts when payment lands."
        )
    return {
        "found": True,
        "status": status,
        "order_id": order_id,
        "total_cents": order["total_cents"],
        "pickup_at": order.get("pickup_at"),
        "expires_at": order.get("expires_at"),
        "message": message,
    }


async def apply_checkout_completed(session: dict) -> str:
    """Apply a Checkout Session. Returns paid, mismatch, missing, or ignored."""
    metadata = session.get("metadata") or {}
    order_id = metadata.get("order_id")
    tenant_id = metadata.get("tenant_id")
    if not order_id or not tenant_id:
        return "missing"
    order = await get_order(tenant_id, order_id)
    if not order:
        return "missing"
    if order["status"] == "paid":
        return "paid"
    if order["status"] not in ("draft", "link_sent"):
        return "ignored"
    amount = session.get("amount_total")
    if amount is None or int(amount) != int(order["total_cents"]):
        logger.error(
            f"Stripe amount {amount} did not match order {order_id} total {order['total_cents']}"
        )
        return "mismatch"
    db = await get_db()
    try:
        await db.execute(
            "UPDATE orders SET status = 'paid' WHERE tenant_id = ? AND id = ? AND status != 'paid'",
            (tenant_id, order_id),
        )
        await db.commit()
    finally:
        await db.close()
    ready = order.get("pickup_at") or "the held time"
    send_sms(
        order.get("customer_phone") or "",
        f"Paid. Order {order_id} will be ready at {ready}.",
    )
    return "paid"


async def refresh_legacy_restaurant_agents() -> int:
    """Replace the imported restaurant prompt while it still names the sample dishes."""
    path = Path(__file__).parent / "agents" / "restaurant_host.json"
    if not path.exists():
        return 0
    fresh = json.loads(path.read_text())
    db = await get_db()
    updated = 0
    try:
        cursor = await db.execute(
            "SELECT tenant_id, system_prompt FROM agents WHERE id = ?",
            ("restaurant_host",),
        )
        rows = await cursor.fetchall()
        for row in rows:
            prompt = row["system_prompt"] or ""
            if LEGACY_PROMPT_MARKER not in prompt:
                continue
            await db.execute(
                """
                UPDATE agents
                SET system_prompt = ?, greeting = ?, voice_id = ?, guardrail_level = ?,
                    allowed_tools = ?, states = ?, max_turns = ?, max_duration_seconds = ?,
                    escalation_triggers = ?, description = ?, updated_at = datetime('now')
                WHERE tenant_id = ? AND id = 'restaurant_host'
                """,
                (
                    fresh["system_prompt"],
                    fresh.get("greeting", ""),
                    fresh.get("voice_id", "en-US-Chirp3-HD-Charon"),
                    fresh.get("guardrail_level", 0.8),
                    json.dumps(fresh.get("allowed_tools") or []),
                    json.dumps(fresh.get("states") or []),
                    fresh.get("max_turns", 20),
                    fresh.get("max_duration_seconds", 240),
                    json.dumps(fresh.get("escalation_triggers") or []),
                    fresh.get("description", ""),
                    row["tenant_id"],
                ),
            )
            updated += 1
        await db.commit()
    finally:
        await db.close()
    if updated:
        logger.info(f"Refreshed {updated} legacy restaurant host row(s)")
    return updated


async def seed_restaurant_menus() -> int:
    """Insert the demo menu once for each tenant that has the restaurant host and no items."""
    db = await get_db()
    seeded = 0
    try:
        cursor = await db.execute(
            "SELECT DISTINCT tenant_id FROM agents WHERE id = ?",
            ("restaurant_host",),
        )
        tenant_ids = [row["tenant_id"] for row in await cursor.fetchall()]
        for tenant_id in tenant_ids:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM menu_items WHERE tenant_id = ?",
                (tenant_id,),
            )
            if (await cursor.fetchone())[0] > 0:
                continue
            for item in DEMO_ITEMS:
                await db.execute(
                    """
                    INSERT INTO menu_items
                        (id, tenant_id, name, description, price_cents, available, choice_options)
                    VALUES (?, ?, ?, ?, ?, ?, '[]')
                    """,
                    (
                        item["id"],
                        tenant_id,
                        item["name"],
                        item["description"],
                        item["price_cents"],
                        item["available"],
                    ),
                )
            for weekday in range(7):
                await db.execute(
                    """
                    INSERT INTO hours
                        (id, tenant_id, weekday, open_time, close_time, slot_minutes, capacity)
                    VALUES (?, ?, ?, '19:10', '20:00', 15, 1)
                    """,
                    (f"{tenant_id}-hours-{weekday}", tenant_id, weekday),
                )
            seeded += 1
        await db.commit()
    finally:
        await db.close()
    if seeded:
        logger.info(f"Seeded demo menus for {seeded} tenant(s)")
    return seeded
