"""
Superactive — Database Layer

SQLite via aiosqlite. All CRUD for tenants, users, agents, campaigns,
contacts, calls, and leads. Designed so swapping to Postgres is a
one-file change (replace aiosqlite with asyncpg, TEXT JSON → JSONB).

On first startup, migrates existing flat-file data into the database.
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiosqlite
from loguru import logger


DB_PATH = Path(__file__).parent / "data" / "superactive.db"

# ── Schema ───────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    twilio_sid TEXT DEFAULT '',
    twilio_token TEXT DEFAULT '',
    twilio_phone TEXT DEFAULT '',
    public_url TEXT DEFAULT '',
    plan TEXT DEFAULT 'starter',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    role TEXT DEFAULT 'admin',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    business_type TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    greeting TEXT DEFAULT 'Hello, how can I help you today?',
    voice_id TEXT DEFAULT 'en-US-Chirp3-HD-Charon',
    guardrail_level REAL DEFAULT 0.5,
    allowed_tools TEXT DEFAULT '[]',
    webhook_url TEXT,
    webhook_headers TEXT DEFAULT '{}',
    states TEXT DEFAULT '[]',
    max_turns INTEGER DEFAULT 20,
    max_duration_seconds INTEGER DEFAULT 300,
    escalation_triggers TEXT DEFAULT '[]',
    active INTEGER DEFAULT 1,
    description TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    status TEXT DEFAULT 'draft',
    total_contacts INTEGER DEFAULT 0,
    called INTEGER DEFAULT 0,
    booked INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    schedule TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    name TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    call_sid TEXT,
    outcome TEXT,
    extra TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calls (
    call_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    agent_id TEXT NOT NULL,
    business_type TEXT DEFAULT '',
    started_at TEXT,
    ended_at TEXT,
    duration_seconds INTEGER DEFAULT 0,
    outcome TEXT DEFAULT 'in_progress',
    outcome_detail TEXT DEFAULT '',
    states_visited TEXT DEFAULT '[]',
    hang_up_state TEXT,
    state_transitions TEXT DEFAULT '[]',
    total_turns INTEGER DEFAULT 0,
    frustration_triggered INTEGER DEFAULT 0,
    escalation_triggered INTEGER DEFAULT 0,
    repeat_detected INTEGER DEFAULT 0,
    tools_used TEXT DEFAULT '[]',
    cost_per_minute REAL DEFAULT 0.028,
    cost_estimate REAL DEFAULT 0.0,
    transcript TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    type TEXT DEFAULT 'lead',
    name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    interest TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    priority TEXT DEFAULT 'medium',
    date TEXT,
    time TEXT,
    reason TEXT,
    confirmation TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_agents_tenant ON agents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_tenant ON campaigns(tenant_id);
CREATE INDEX IF NOT EXISTS idx_contacts_campaign ON contacts(campaign_id);
CREATE INDEX IF NOT EXISTS idx_calls_tenant ON calls(tenant_id);
CREATE INDEX IF NOT EXISTS idx_calls_started ON calls(started_at);
CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
"""


# ── Connection ───────────────────────────────────────────────────────

async def get_db() -> aiosqlite.Connection:
    """Get an async SQLite connection with WAL mode and foreign keys."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Create tables and run migration if needed."""
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
        logger.info("📦 Database initialized")

        # Check if migration is needed (no tenants = first run)
        cursor = await db.execute("SELECT COUNT(*) FROM tenants")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await _migrate_from_files(db)
    finally:
        await db.close()


# ── Tenant CRUD ──────────────────────────────────────────────────────

async def db_create_tenant(name: str, email: str) -> dict:
    """Create a new tenant. Returns the tenant dict."""
    tenant_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO tenants (id, name, email) VALUES (?, ?, ?)",
            (tenant_id, name, email),
        )
        await db.commit()
        return {"id": tenant_id, "name": name, "email": email, "plan": "starter"}
    finally:
        await db.close()


async def db_get_tenant(tenant_id: str) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def db_update_tenant(tenant_id: str, **fields) -> bool:
    """Update tenant fields. Only updates provided fields."""
    if not fields:
        return False
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [tenant_id]
    db = await get_db()
    try:
        await db.execute(f"UPDATE tenants SET {sets} WHERE id = ?", vals)
        await db.commit()
        return True
    finally:
        await db.close()


# ── User CRUD ────────────────────────────────────────────────────────

async def db_create_user(email: str, password_hash: str, tenant_id: str, role: str = "admin") -> dict:
    user_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO users (id, email, password_hash, tenant_id, role) VALUES (?, ?, ?, ?, ?)",
            (user_id, email, password_hash, tenant_id, role),
        )
        await db.commit()
        return {"id": user_id, "email": email, "tenant_id": tenant_id, "role": role}
    finally:
        await db.close()


async def db_get_user_by_email(email: str) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT u.*, t.name as tenant_name FROM users u JOIN tenants t ON u.tenant_id = t.id WHERE u.email = ?",
            (email,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ── Agent CRUD ───────────────────────────────────────────────────────

def _agent_row_to_dict(row: dict) -> dict:
    """Convert a DB row to AgentConfig-compatible dict."""
    d = dict(row)
    for key in ("allowed_tools", "states", "escalation_triggers"):
        if isinstance(d.get(key), str):
            d[key] = json.loads(d[key])
    if isinstance(d.get("webhook_headers"), str):
        d["webhook_headers"] = json.loads(d["webhook_headers"])
    d["active"] = bool(d.get("active", 1))
    return d


def _agent_dict_to_row(agent: dict, tenant_id: str) -> dict:
    """Convert an AgentConfig dict to DB row values."""
    d = dict(agent)
    d["tenant_id"] = tenant_id
    for key in ("allowed_tools", "states", "escalation_triggers"):
        if isinstance(d.get(key), (list, tuple)):
            d[key] = json.dumps(d[key])
    if isinstance(d.get("webhook_headers"), dict):
        d["webhook_headers"] = json.dumps(d["webhook_headers"])
    d["active"] = 1 if d.get("active", True) else 0
    d["updated_at"] = datetime.now().isoformat()
    return d


async def db_load_agent(agent_id: str, tenant_id: str = None) -> Optional[dict]:
    """Load an agent by ID. If tenant_id is None, loads from any tenant (for telephony)."""
    db = await get_db()
    try:
        if tenant_id:
            cursor = await db.execute(
                "SELECT * FROM agents WHERE id = ? AND tenant_id = ?",
                (agent_id, tenant_id),
            )
        else:
            cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = await cursor.fetchone()
        return _agent_row_to_dict(row) if row else None
    finally:
        await db.close()


async def db_save_agent(agent: dict, tenant_id: str) -> bool:
    """Insert or update an agent."""
    row = _agent_dict_to_row(agent, tenant_id)
    cols = ["id", "tenant_id", "name", "business_type", "system_prompt", "greeting",
            "voice_id", "guardrail_level", "allowed_tools", "webhook_url", "webhook_headers",
            "states", "max_turns", "max_duration_seconds", "escalation_triggers",
            "active", "description", "updated_at"]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    vals = [row.get(c, "") for c in cols]

    db = await get_db()
    try:
        await db.execute(
            f"INSERT OR REPLACE INTO agents ({col_names}) VALUES ({placeholders})",
            vals,
        )
        await db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save agent {agent.get('id')}: {e}")
        return False
    finally:
        await db.close()


async def db_list_agents(tenant_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agents WHERE tenant_id = ? ORDER BY name", (tenant_id,)
        )
        rows = await cursor.fetchall()
        return [_agent_row_to_dict(r) for r in rows]
    finally:
        await db.close()


async def db_delete_agent(agent_id: str, tenant_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM agents WHERE id = ? AND tenant_id = ?",
            (agent_id, tenant_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ── Campaign CRUD ────────────────────────────────────────────────────

def _campaign_row_to_dict(row: dict) -> dict:
    d = dict(row)
    if isinstance(d.get("schedule"), str) and d["schedule"]:
        d["schedule"] = json.loads(d["schedule"])
    return d


async def db_save_campaign(campaign: dict, tenant_id: str) -> bool:
    db = await get_db()
    try:
        schedule = campaign.get("schedule")
        if isinstance(schedule, dict):
            schedule = json.dumps(schedule)
        await db.execute(
            """INSERT OR REPLACE INTO campaigns
               (id, tenant_id, name, agent_id, status, total_contacts, called, booked, failed, schedule, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (campaign["id"], tenant_id, campaign["name"], campaign["agent_id"],
             campaign.get("status", "draft"), campaign.get("total_contacts", 0),
             campaign.get("called", 0), campaign.get("booked", 0),
             campaign.get("failed", 0), schedule,
             datetime.now().isoformat()),
        )
        await db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save campaign {campaign.get('id')}: {e}")
        return False
    finally:
        await db.close()


async def db_load_campaign(campaign_id: str, tenant_id: str = None) -> Optional[dict]:
    db = await get_db()
    try:
        if tenant_id:
            cursor = await db.execute(
                "SELECT * FROM campaigns WHERE id = ? AND tenant_id = ?",
                (campaign_id, tenant_id),
            )
        else:
            cursor = await db.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        campaign = _campaign_row_to_dict(row)

        # Load contacts
        cursor2 = await db.execute(
            "SELECT * FROM contacts WHERE campaign_id = ? ORDER BY id", (campaign_id,)
        )
        contacts = []
        for c in await cursor2.fetchall():
            cd = dict(c)
            if isinstance(cd.get("extra"), str):
                cd["extra"] = json.loads(cd["extra"])
            contacts.append(cd)
        campaign["contacts"] = contacts
        return campaign
    finally:
        await db.close()


async def db_list_campaigns(tenant_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM campaigns WHERE tenant_id = ? ORDER BY created_at DESC",
            (tenant_id,),
        )
        rows = await cursor.fetchall()
        campaigns = []
        for row in rows:
            c = _campaign_row_to_dict(row)
            # Count contacts instead of loading them all for list view
            cursor2 = await db.execute(
                "SELECT COUNT(*) FROM contacts WHERE campaign_id = ?", (c["id"],)
            )
            c["total_contacts"] = (await cursor2.fetchone())[0]
            campaigns.append(c)
        return campaigns
    finally:
        await db.close()


async def db_delete_campaign(campaign_id: str, tenant_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM campaigns WHERE id = ? AND tenant_id = ?",
            (campaign_id, tenant_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def db_update_campaign_fields(campaign_id: str, **fields) -> bool:
    """Update specific fields on a campaign."""
    if not fields:
        return False
    fields["updated_at"] = datetime.now().isoformat()
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [campaign_id]
    db = await get_db()
    try:
        await db.execute(f"UPDATE campaigns SET {sets} WHERE id = ?", vals)
        await db.commit()
        return True
    finally:
        await db.close()


# ── Contact CRUD ─────────────────────────────────────────────────────

async def db_save_contacts(campaign_id: str, contacts: list[dict]) -> int:
    """Replace all contacts for a campaign. Returns count inserted."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM contacts WHERE campaign_id = ?", (campaign_id,))
        for c in contacts:
            extra = c.get("extra", {})
            if isinstance(extra, dict):
                extra = json.dumps(extra)
            await db.execute(
                "INSERT INTO contacts (campaign_id, phone, name, status, extra) VALUES (?, ?, ?, ?, ?)",
                (campaign_id, c["phone"], c.get("name", ""), c.get("status", "pending"), extra),
            )
        await db.commit()
        return len(contacts)
    finally:
        await db.close()


async def db_get_contacts(campaign_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM contacts WHERE campaign_id = ? ORDER BY id", (campaign_id,)
        )
        rows = await cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("extra"), str):
                d["extra"] = json.loads(d["extra"])
            results.append(d)
        return results
    finally:
        await db.close()


async def db_update_contact(contact_id: int, **fields) -> bool:
    if not fields:
        return False
    # Serialize extra if present
    if "extra" in fields and isinstance(fields["extra"], dict):
        fields["extra"] = json.dumps(fields["extra"])
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [contact_id]
    db = await get_db()
    try:
        await db.execute(f"UPDATE contacts SET {sets} WHERE id = ?", vals)
        await db.commit()
        return True
    finally:
        await db.close()


async def db_update_contact_by_index(campaign_id: str, index: int, **fields) -> bool:
    """Update a contact by its position in the campaign (for dialer compatibility)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM contacts WHERE campaign_id = ? ORDER BY id LIMIT 1 OFFSET ?",
            (campaign_id, index),
        )
        row = await cursor.fetchone()
        if not row:
            return False
        await db.close()
        return await db_update_contact(row["id"], **fields)
    except Exception:
        await db.close()
        return False


# ── Call CRUD ────────────────────────────────────────────────────────

async def db_persist_call(call_log: dict, tenant_id: str):
    """Persist a completed call log to the database."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO calls
               (call_id, tenant_id, agent_id, business_type, started_at, ended_at,
                duration_seconds, outcome, outcome_detail, states_visited, hang_up_state,
                state_transitions, total_turns, frustration_triggered, escalation_triggered,
                repeat_detected, tools_used, cost_per_minute, cost_estimate, transcript)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (call_log["call_id"], tenant_id, call_log["agent_id"],
             call_log.get("business_type", ""),
             call_log.get("started_at"), call_log.get("ended_at"),
             call_log.get("duration_seconds", 0),
             call_log.get("outcome", "completed"),
             call_log.get("outcome_detail", ""),
             json.dumps(call_log.get("states_visited", [])),
             call_log.get("hang_up_state"),
             json.dumps(call_log.get("state_transitions", [])),
             call_log.get("total_turns", 0),
             1 if call_log.get("frustration_triggered") else 0,
             1 if call_log.get("escalation_triggered") else 0,
             1 if call_log.get("repeat_detected") else 0,
             json.dumps(call_log.get("tools_used", [])),
             call_log.get("cost_per_minute", 0.028),
             call_log.get("cost_estimate", 0.0),
             json.dumps(call_log.get("transcript", []))),
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to persist call {call_log.get('call_id')}: {e}")
    finally:
        await db.close()


def _call_row_to_dict(row: dict) -> dict:
    d = dict(row)
    for key in ("states_visited", "state_transitions", "tools_used", "transcript"):
        if isinstance(d.get(key), str):
            d[key] = json.loads(d[key])
    d["frustration_triggered"] = bool(d.get("frustration_triggered", 0))
    d["escalation_triggered"] = bool(d.get("escalation_triggered", 0))
    d["repeat_detected"] = bool(d.get("repeat_detected", 0))
    return d


async def db_get_calls(tenant_id: str, days: int = 7, agent_id: str = None,
                       business_type: str = None) -> list[dict]:
    db = await get_db()
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query = "SELECT * FROM calls WHERE tenant_id = ? AND started_at >= ?"
        params: list = [tenant_id, cutoff]
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if business_type:
            query += " AND business_type = ?"
            params.append(business_type)
        query += " ORDER BY started_at DESC"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [_call_row_to_dict(r) for r in rows]
    finally:
        await db.close()


async def db_get_analytics(tenant_id: str, days: int = 30) -> dict:
    """Aggregate analytics for a tenant."""
    db = await get_db()
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        prev_cutoff = (datetime.now() - timedelta(days=days * 2)).isoformat()

        # Current period
        cursor = await db.execute(
            "SELECT * FROM calls WHERE tenant_id = ? AND started_at >= ?",
            (tenant_id, cutoff),
        )
        current_calls = [_call_row_to_dict(r) for r in await cursor.fetchall()]

        # Previous period
        cursor = await db.execute(
            "SELECT * FROM calls WHERE tenant_id = ? AND started_at >= ? AND started_at < ?",
            (tenant_id, prev_cutoff, cutoff),
        )
        previous_calls = [_call_row_to_dict(r) for r in await cursor.fetchall()]

        def _delta(current: float, previous: float) -> str:
            if previous == 0:
                return "+100%" if current > 0 else "0%"
            d = ((current - previous) / previous) * 100
            return f"{'+' if d >= 0 else ''}{d:.0f}%"

        if not current_calls:
            empty = {"total_calls": "0%", "avg_duration": "0%", "booking_rate": "0%", "frustration_rate": "0%"}
            return {
                "total_calls": 0, "avg_duration": 0, "booking_rate": 0, "frustration_rate": 0,
                "total_cost": 0, "avg_cost_per_call": 0,
                "outcomes": {"booked": 0, "transferred": 0, "completed": 0, "hung_up": 0},
                "agent_performance": [], "hang_up_heatmap": {},
                "calls_per_day": [], "changes": empty,
            }

        total = len(current_calls)
        total_duration = sum(c["duration_seconds"] for c in current_calls)
        total_cost = sum(c.get("cost_estimate", 0) for c in current_calls)
        booked = sum(1 for c in current_calls if c["outcome"] == "booked")
        transferred = sum(1 for c in current_calls if c["outcome"] == "transferred")
        hung_up = sum(1 for c in current_calls if c["outcome"] == "hung_up")
        completed = sum(1 for c in current_calls if c["outcome"] == "completed")
        frustrated = sum(1 for c in current_calls if c.get("frustration_triggered"))

        avg_dur = round(total_duration / total) if total else 0
        book_rate = round(booked / total * 100, 1) if total else 0
        frust_rate = round(frustrated / total * 100, 1) if total else 0

        prev_total = len(previous_calls)
        prev_dur = round(sum(c["duration_seconds"] for c in previous_calls) / prev_total) if prev_total else 0
        prev_booked = sum(1 for c in previous_calls if c["outcome"] == "booked")
        prev_book_rate = round(prev_booked / prev_total * 100, 1) if prev_total else 0
        prev_frustrated = sum(1 for c in previous_calls if c.get("frustration_triggered"))
        prev_frust_rate = round(prev_frustrated / prev_total * 100, 1) if prev_total else 0

        changes = {
            "total_calls": _delta(total, prev_total),
            "avg_duration": _delta(avg_dur, prev_dur),
            "booking_rate": _delta(book_rate, prev_book_rate),
            "frustration_rate": _delta(frust_rate, prev_frust_rate),
        }

        # Calls per day
        day_counts: dict[str, int] = {}
        for c in current_calls:
            day = c["started_at"][:10]
            day_counts[day] = day_counts.get(day, 0) + 1
        calls_per_day = []
        for i in range(days):
            d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            calls_per_day.append({"date": d, "count": day_counts.get(d, 0)})

        # Per-agent breakdown
        agent_stats: dict = {}
        for call in current_calls:
            aid = call["agent_id"]
            if aid not in agent_stats:
                agent_stats[aid] = {"calls": 0, "booked": 0, "total_duration": 0, "business_type": call.get("business_type", "")}
            agent_stats[aid]["calls"] += 1
            agent_stats[aid]["total_duration"] += call["duration_seconds"]
            if call["outcome"] == "booked":
                agent_stats[aid]["booked"] += 1

        agent_performance = [
            {
                "agent_id": aid,
                "business_type": s["business_type"],
                "calls": s["calls"],
                "conversion_rate": round(s["booked"] / s["calls"] * 100, 1) if s["calls"] else 0,
                "avg_duration": round(s["total_duration"] / s["calls"]) if s["calls"] else 0,
            }
            for aid, s in agent_stats.items()
        ]

        hang_up_states: dict = {}
        for call in current_calls:
            if call.get("hang_up_state"):
                hang_up_states[call["hang_up_state"]] = hang_up_states.get(call["hang_up_state"], 0) + 1

        return {
            "total_calls": total, "avg_duration": avg_dur, "booking_rate": book_rate,
            "frustration_rate": frust_rate, "total_cost": round(total_cost, 2),
            "avg_cost_per_call": round(total_cost / total, 4) if total else 0,
            "outcomes": {"booked": booked, "transferred": transferred, "completed": completed, "hung_up": hung_up},
            "agent_performance": agent_performance, "hang_up_heatmap": hang_up_states,
            "calls_per_day": calls_per_day, "changes": changes,
        }
    finally:
        await db.close()


# ── Lead CRUD ────────────────────────────────────────────────────────

async def db_log_lead(lead: dict, tenant_id: str):
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO leads (tenant_id, type, name, phone, interest, notes, priority, date, time, reason, confirmation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tenant_id, lead.get("type", "lead"), lead.get("name", ""),
             lead.get("phone", ""), lead.get("interest", ""),
             lead.get("notes", ""), lead.get("priority", "medium"),
             lead.get("date", ""), lead.get("time", ""),
             lead.get("reason", ""), lead.get("confirmation", "")),
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to log lead: {e}")
    finally:
        await db.close()


async def db_lookup_client(phone: str, tenant_id: str) -> Optional[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM leads WHERE tenant_id = ? AND phone = ? ORDER BY created_at DESC LIMIT 1",
            (tenant_id, phone),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ── Migration from Flat Files ────────────────────────────────────────

async def _migrate_from_files(db: aiosqlite.Connection):
    """One-time migration of existing JSON/JSONL files into the database."""
    logger.info("📦 Migrating existing file data to database...")

    # Read settings for default tenant info
    settings_file = Path(__file__).parent / "data" / "settings.json"
    settings = {}
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
        except Exception:
            pass

    # Create default tenant
    default_tenant_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO tenants (id, name, email, public_url) VALUES (?, ?, ?, ?)",
        (default_tenant_id,
         settings.get("business_name", "Superactive Demo"),
         settings.get("owner_email", "admin@superactive.ai"),
         settings.get("public_url", "")),
    )

    # Create default admin user (password: "admin" — must be changed!)
    from auth import hash_password
    await db.execute(
        "INSERT INTO users (id, email, password_hash, tenant_id, role) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), settings.get("owner_email", "admin@superactive.ai"),
         hash_password("admin"), default_tenant_id, "admin"),
    )

    # Migrate agents
    agents_dir = Path(__file__).parent / "agents"
    if agents_dir.exists():
        for path in agents_dir.glob("*.json"):
            try:
                agent = json.loads(path.read_text())
                agent_id = agent.get("id", path.stem)
                await db.execute(
                    """INSERT OR IGNORE INTO agents
                       (id, tenant_id, name, business_type, system_prompt, greeting, voice_id,
                        guardrail_level, allowed_tools, webhook_url, webhook_headers, states,
                        max_turns, max_duration_seconds, escalation_triggers, active, description)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (agent_id, default_tenant_id,
                     agent.get("name", agent_id),
                     agent.get("business_type", "general"),
                     agent.get("system_prompt", ""),
                     agent.get("greeting", "Hello!"),
                     agent.get("voice_id", "en-US-Chirp3-HD-Charon"),
                     agent.get("guardrail_level", 0.5),
                     json.dumps(agent.get("allowed_tools", [])),
                     agent.get("webhook_url"),
                     json.dumps(agent.get("webhook_headers", {})),
                     json.dumps(agent.get("states", [])),
                     agent.get("max_turns", 20),
                     agent.get("max_duration_seconds", 300),
                     json.dumps(agent.get("escalation_triggers", [])),
                     1 if agent.get("active", True) else 0,
                     agent.get("description", "")),
                )
                logger.info(f"  ✅ Migrated agent: {agent_id}")
            except Exception as e:
                logger.error(f"  ❌ Failed to migrate agent {path.name}: {e}")

    # Migrate campaigns + contacts
    campaigns_dir = Path(__file__).parent / "data" / "campaigns"
    if campaigns_dir.exists():
        for path in campaigns_dir.glob("*.json"):
            try:
                campaign = json.loads(path.read_text())
                campaign_id = campaign.get("id", path.stem)
                schedule = campaign.get("schedule")
                if isinstance(schedule, dict):
                    schedule = json.dumps(schedule)
                await db.execute(
                    """INSERT OR IGNORE INTO campaigns
                       (id, tenant_id, name, agent_id, status, total_contacts, called, booked, failed, schedule)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (campaign_id, default_tenant_id,
                     campaign.get("name", campaign_id),
                     campaign.get("agent_id", ""),
                     campaign.get("status", "draft"),
                     campaign.get("total_contacts", 0),
                     campaign.get("called", 0),
                     campaign.get("booked", 0),
                     campaign.get("failed", 0),
                     schedule),
                )
                # Migrate contacts
                for contact in campaign.get("contacts", []):
                    extra = contact.get("extra", {})
                    if isinstance(extra, dict):
                        extra = json.dumps(extra)
                    await db.execute(
                        "INSERT INTO contacts (campaign_id, phone, name, status, call_sid, outcome, extra) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (campaign_id, contact.get("phone", ""),
                         contact.get("name", ""), contact.get("status", "pending"),
                         contact.get("call_sid"), contact.get("outcome"), extra),
                    )
                logger.info(f"  ✅ Migrated campaign: {campaign_id} ({len(campaign.get('contacts', []))} contacts)")
            except Exception as e:
                logger.error(f"  ❌ Failed to migrate campaign {path.name}: {e}")

    # Migrate call logs
    calls_dir = Path(__file__).parent / "data" / "calls"
    if calls_dir.exists():
        call_count = 0
        for path in calls_dir.glob("*.jsonl"):
            try:
                with open(path) as f:
                    for line in f:
                        try:
                            call = json.loads(line.strip())
                            await db.execute(
                                """INSERT OR IGNORE INTO calls
                                   (call_id, tenant_id, agent_id, business_type, started_at, ended_at,
                                    duration_seconds, outcome, outcome_detail, states_visited,
                                    hang_up_state, state_transitions, total_turns,
                                    frustration_triggered, escalation_triggered, repeat_detected,
                                    tools_used, cost_per_minute, cost_estimate, transcript)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (call.get("call_id", str(uuid.uuid4())),
                                 default_tenant_id,
                                 call.get("agent_id", ""),
                                 call.get("business_type", ""),
                                 call.get("started_at", ""),
                                 call.get("ended_at"),
                                 call.get("duration_seconds", 0),
                                 call.get("outcome", "completed"),
                                 call.get("outcome_detail", ""),
                                 json.dumps(call.get("states_visited", [])),
                                 call.get("hang_up_state"),
                                 json.dumps(call.get("state_transitions", [])),
                                 call.get("total_turns", 0),
                                 1 if call.get("frustration_triggered") else 0,
                                 1 if call.get("escalation_triggered") else 0,
                                 1 if call.get("repeat_detected") else 0,
                                 json.dumps(call.get("tools_used", [])),
                                 call.get("cost_per_minute", 0.028),
                                 call.get("cost_estimate", 0.0),
                                 json.dumps(call.get("transcript", []))),
                            )
                            call_count += 1
                        except Exception:
                            continue
            except Exception as e:
                logger.error(f"  ❌ Failed to migrate calls from {path.name}: {e}")
        if call_count:
            logger.info(f"  ✅ Migrated {call_count} call logs")

    # Migrate leads
    leads_file = Path(__file__).parent / "data" / "leads.jsonl"
    if leads_file.exists():
        lead_count = 0
        try:
            with open(leads_file) as f:
                for line in f:
                    try:
                        lead = json.loads(line.strip())
                        await db.execute(
                            """INSERT INTO leads (tenant_id, type, name, phone, interest, notes, priority, date, time, reason, confirmation)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (default_tenant_id, lead.get("type", "lead"),
                             lead.get("name", ""), lead.get("phone", ""),
                             lead.get("interest", ""), lead.get("notes", ""),
                             lead.get("priority", "medium"), lead.get("date", ""),
                             lead.get("time", ""), lead.get("reason", ""),
                             lead.get("confirmation", "")),
                        )
                        lead_count += 1
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"  ❌ Failed to migrate leads: {e}")
        if lead_count:
            logger.info(f"  ✅ Migrated {lead_count} leads")

    await db.commit()
    logger.info(f"📦 Migration complete! Default tenant ID: {default_tenant_id}")
    logger.warning("⚠️ Default admin password is 'admin' — change it immediately!")
