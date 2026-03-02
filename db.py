"""
Superactive — Database Layer (PostgreSQL)

PostgreSQL via asyncpg. All CRUD for tenants, users, agents, campaigns,
contacts, calls, and leads. 
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import asyncpg
from loguru import logger
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

# Instrument AsyncPG globally
AsyncPGInstrumentor().instrument()


# Database connection configuration
POSTGRES_USER = os.getenv("POSTGRES_USER", "superactive")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "superactive")
POSTGRES_DB = os.getenv("POSTGRES_DB", "superactive")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DSN = f"postgres://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Global pool instance
_pool: Optional[asyncpg.Pool] = None

# ── Schema ───────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    telephony_provider TEXT DEFAULT 'telnyx',
    backup_provider TEXT DEFAULT '',
    telnyx_api_key TEXT DEFAULT '',
    telnyx_connection_id TEXT DEFAULT '',
    telnyx_phone TEXT DEFAULT '',
    twilio_account_sid TEXT DEFAULT '',
    twilio_auth_token TEXT DEFAULT '',
    twilio_phone TEXT DEFAULT '',
    api_key TEXT UNIQUE,
    webhook_url TEXT DEFAULT '',
    public_url TEXT DEFAULT '',
    plan TEXT DEFAULT 'starter',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    role TEXT DEFAULT 'admin',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    business_type TEXT NOT NULL,
    agent_type TEXT DEFAULT 'inbound',
    system_prompt TEXT NOT NULL,
    greeting TEXT DEFAULT 'Hello, how can I help you today?',
    outbound_greeting TEXT DEFAULT '',
    voice_id TEXT DEFAULT 'en-US-Chirp3-HD-Charon',
    guardrail_level REAL DEFAULT 0.5,
    allowed_tools JSONB DEFAULT '[]',
    webhook_url TEXT,
    webhook_headers JSONB DEFAULT '{}',
    webhook_payload_mapping JSONB DEFAULT '{}',
    states JSONB DEFAULT '[]',
    max_turns INTEGER DEFAULT 20,
    max_duration_seconds INTEGER DEFAULT 300,
    escalation_triggers JSONB DEFAULT '[]',
    frustration_tolerance INTEGER DEFAULT 1,
    loop_sensitivity INTEGER DEFAULT 2,
    active INTEGER DEFAULT 1,
    description TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
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
    schedule JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    name TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    call_sid TEXT,
    outcome TEXT,
    extra JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS calls (
    call_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    agent_id TEXT NOT NULL,
    business_type TEXT DEFAULT '',
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER DEFAULT 0,
    outcome TEXT DEFAULT 'in_progress',
    outcome_detail TEXT DEFAULT '',
    states_visited JSONB DEFAULT '[]',
    hang_up_state TEXT,
    state_transitions JSONB DEFAULT '[]',
    total_turns INTEGER DEFAULT 0,
    frustration_triggered INTEGER DEFAULT 0,
    escalation_triggered INTEGER DEFAULT 0,
    repeat_detected INTEGER DEFAULT 0,
    tools_used JSONB DEFAULT '[]',
    cost_per_minute REAL DEFAULT 0.028,
    cost_estimate REAL DEFAULT 0.0,
    transcript JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
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

async def get_pool() -> asyncpg.Pool:
    """Get the asyncpg connection pool."""
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(DSN, min_size=5, max_size=20)
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise
    return _pool


async def init_db():
    """Create tables (no flat file migration)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            # asyncpg executescript equivalent is multiple commands
            # but standard Execute works for schema dumps
            await conn.execute(SCHEMA)
            logger.info("📦 PostgreSQL Database initialized (Schema created)")
            
            # Note: Removed SQLite column auto-migrations and file imports since
            # this is a fresh setup targeting the full schema.
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")


# ── Tenant CRUD ──────────────────────────────────────────────────────

async def db_create_tenant(name: str, email: str) -> dict:
    """Create a new tenant. Returns the tenant dict."""
    tenant_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO tenants (id, name, email) VALUES ($1, $2, $3)",
            tenant_id, name, email
        )
        return {"id": tenant_id, "name": name, "email": email, "plan": "starter"}


async def db_get_tenant(tenant_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tenants WHERE id = $1", tenant_id)
        return dict(row) if row else None


_TENANT_UPDATABLE = {
    "name", "email", "public_url", "plan", 
    "telephony_provider", "backup_provider",
    "telnyx_api_key", "telnyx_connection_id", "telnyx_phone",
    "twilio_account_sid", "twilio_auth_token", "twilio_phone",
    "webhook_url",
}

async def db_update_tenant(tenant_id: str, **fields) -> bool:
    safe_fields = {k: v for k, v in fields.items() if k in _TENANT_UPDATABLE}
    if not safe_fields:
        return False
    
    # Construct parameterized update query for postgres ($1, $2, etc)
    sets = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(safe_fields.keys()))
    vals = list(safe_fields.values())
    vals.append(tenant_id)
    query = f"UPDATE tenants SET {sets} WHERE id = ${len(vals)}"
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(query, *vals)
        return res.endswith("1")  # Returns something like 'UPDATE 1'


async def get_telephony_credentials(tenant_id: str) -> dict:
    """Get telephony credentials for a tenant, including primary provider."""
    tenant = await db_get_tenant(tenant_id)
    t_dict = tenant or {}
    
    return {
        "provider": t_dict.get("telephony_provider") or "telnyx",
        "backup_provider": t_dict.get("backup_provider") or "",
        "telnyx": {
            "api_key": t_dict.get("telnyx_api_key") or os.getenv("TELNYX_API_KEY", ""),
            "connection_id": t_dict.get("telnyx_connection_id") or os.getenv("TELNYX_CONNECTION_ID", ""),
            "phone_number": t_dict.get("telnyx_phone") or os.getenv("TELNYX_PHONE_NUMBER", ""),
        },
        "twilio": {
            "account_sid": t_dict.get("twilio_account_sid") or os.getenv("TWILIO_ACCOUNT_SID", ""),
            "auth_token": t_dict.get("twilio_auth_token") or os.getenv("TWILIO_AUTH_TOKEN", ""),
            "phone_number": t_dict.get("twilio_phone") or os.getenv("TWILIO_PHONE_NUMBER", ""),
        }
    }


# ── User CRUD ────────────────────────────────────────────────────────

async def db_create_user(email: str, password_hash: str, tenant_id: str, role: str = "admin") -> dict:
    user_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (id, email, password_hash, tenant_id, role) VALUES ($1, $2, $3, $4, $5)",
            user_id, email, password_hash, tenant_id, role
        )
        return {"id": user_id, "email": email, "tenant_id": tenant_id, "role": role}


async def db_get_user_by_email(email: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT u.*, t.name as tenant_name FROM users u JOIN tenants t ON u.tenant_id = t.id WHERE u.email = $1",
            email
        )
        return dict(row) if row else None


# ── Agent CRUD ───────────────────────────────────────────────────────

def _agent_row_to_dict(row: asyncpg.Record) -> dict:
    d = dict(row)
    # asyncpg parses JSONB to Python strings, so we still need json.loads, 
    # OR we can depend on pg to auto-cast. usually it returns strings if we select *
    for key in ("allowed_tools", "escalation_triggers", "webhook_headers", "webhook_payload_mapping", "states"):
        if isinstance(d.get(key), str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    
    d["active"] = bool(d.get("active", 1))
    
    # Cast datetime to string for API compatibility
    if "created_at" in d and hasattr(d["created_at"], "isoformat"):
        d["created_at"] = d["created_at"].isoformat()
    if "updated_at" in d and hasattr(d["updated_at"], "isoformat"):
        d["updated_at"] = d["updated_at"].isoformat()
        
    return d


def _agent_dict_to_row(agent: dict, tenant_id: str) -> dict:
    d = dict(agent)
    d["tenant_id"] = tenant_id
    for key in ("allowed_tools", "states", "escalation_triggers"):
        val = d.get(key)
        if isinstance(val, (list, tuple)):
            d[key] = json.dumps(val)
        elif not val:
            d[key] = "[]"
            
    for key in ("webhook_headers", "webhook_payload_mapping"):
        val = d.get(key)
        if isinstance(val, dict):
            d[key] = json.dumps(val)
        elif not val:
            d[key] = "{}"
            
    d["active"] = 1 if d.get("active", True) else 0
    
    # Numeric defaults
    g_level = d.get("guardrail_level")
    d["guardrail_level"] = float(g_level) if g_level not in (None, "") else 0.5
    
    for int_col in ("max_turns", "max_duration_seconds", "frustration_tolerance", "loop_sensitivity"):
        iv = d.get(int_col)
        d[int_col] = int(iv) if iv not in (None, "") else None
        
    return d


async def db_load_agent(agent_id: str, tenant_id: str = None) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if tenant_id:
            row = await conn.fetchrow("SELECT * FROM agents WHERE id = $1 AND tenant_id = $2", agent_id, tenant_id)
        else:
            row = await conn.fetchrow("SELECT * FROM agents WHERE id = $1", agent_id)
        return _agent_row_to_dict(row) if row else None


async def db_save_agent(agent: dict, tenant_id: str) -> bool:
    row = _agent_dict_to_row(agent, tenant_id)
    cols = ["id", "tenant_id", "name", "business_type", "agent_type", "system_prompt", "greeting", "outbound_greeting",
            "voice_id", "guardrail_level", "allowed_tools", "webhook_url", "webhook_headers", "webhook_payload_mapping",
            "states", "max_turns", "max_duration_seconds", "escalation_triggers",
            "frustration_tolerance", "loop_sensitivity", "active", "description"]
    
    # PostgreSQL UPSERT
    placeholders = ", ".join([f"${i+1}" for i in range(len(cols))])
    col_names = ", ".join(cols)
    vals = [row.get(c, "") if c != "active" else row.get(c, 1) for c in cols]
    
    # For ON CONFLICT DO UPDATE
    update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in cols if c not in ('id', 'tenant_id')])
    
    query = f"""
        INSERT INTO agents ({col_names}, updated_at) 
        VALUES ({placeholders}, CURRENT_TIMESTAMP)
        ON CONFLICT (tenant_id, id) 
        DO UPDATE SET {update_set}, updated_at = CURRENT_TIMESTAMP
    """
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(query, *vals)
            return True
        except Exception as e:
            logger.error(f"Failed to save agent {agent.get('id')}: {e}")
            return False


async def db_list_agents(tenant_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM agents WHERE tenant_id = $1 ORDER BY name", tenant_id)
        return [_agent_row_to_dict(r) for r in rows]


async def db_delete_agent(agent_id: str, tenant_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM agents WHERE id = $1 AND tenant_id = $2", agent_id, tenant_id)
        return not res.endswith("0")


# ── Campaign CRUD ────────────────────────────────────────────────────

def _campaign_row_to_dict(row: asyncpg.Record) -> dict:
    d = dict(row)
    if isinstance(d.get("schedule"), str) and d["schedule"]:
        try:
            d["schedule"] = json.loads(d["schedule"])
        except (json.JSONDecodeError, TypeError, ValueError):
            d["schedule"] = {}
            
    if "created_at" in d and hasattr(d["created_at"], "isoformat"):
        d["created_at"] = d["created_at"].isoformat()
    if "updated_at" in d and hasattr(d["updated_at"], "isoformat"):
        d["updated_at"] = d["updated_at"].isoformat()
    return d


async def db_save_campaign(campaign: dict, tenant_id: str) -> bool:
    schedule = campaign.get("schedule")
    if isinstance(schedule, dict):
        schedule = json.dumps(schedule)
        
    query = """
        INSERT INTO campaigns (id, tenant_id, name, agent_id, status, total_contacts, called, booked, failed, schedule, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            agent_id = EXCLUDED.agent_id,
            status = EXCLUDED.status,
            total_contacts = EXCLUDED.total_contacts,
            called = EXCLUDED.called,
            booked = EXCLUDED.booked,
            failed = EXCLUDED.failed,
            schedule = EXCLUDED.schedule,
            updated_at = CURRENT_TIMESTAMP
    """
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                query,
                campaign["id"], tenant_id, campaign["name"], campaign["agent_id"],
                campaign.get("status", "draft"), campaign.get("total_contacts", 0),
                campaign.get("called", 0), campaign.get("booked", 0),
                campaign.get("failed", 0), schedule
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save campaign {campaign.get('id')}: {e}")
            return False


async def db_load_campaign(campaign_id: str, tenant_id: str = None) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if tenant_id:
            row = await conn.fetchrow("SELECT * FROM campaigns WHERE id = $1 AND tenant_id = $2", campaign_id, tenant_id)
        else:
            row = await conn.fetchrow("SELECT * FROM campaigns WHERE id = $1", campaign_id)
            
        if not row:
            return None
            
        campaign = _campaign_row_to_dict(row)

        c_rows = await conn.fetch("SELECT * FROM contacts WHERE campaign_id = $1 ORDER BY id", campaign_id)
        contacts = []
        for c in c_rows:
            cd = dict(c)
            if isinstance(cd.get("extra"), str):
                try: cd["extra"] = json.loads(cd["extra"])
                except (json.JSONDecodeError, TypeError, ValueError): cd["extra"] = {}
            if "created_at" in cd and hasattr(cd["created_at"], "isoformat"):
                cd["created_at"] = cd["created_at"].isoformat()
            contacts.append(cd)
            
        campaign["contacts"] = contacts
        return campaign


async def db_list_campaigns(tenant_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT c.*, COUNT(ct.id) AS contact_count "
            "FROM campaigns c LEFT JOIN contacts ct ON c.id = ct.campaign_id "
            "WHERE c.tenant_id = $1 GROUP BY c.id ORDER BY c.created_at DESC",
            tenant_id
        )
        campaigns = []
        for row in rows:
            c = _campaign_row_to_dict(row)
            c["total_contacts"] = row["contact_count"]
            campaigns.append(c)
        return campaigns


async def db_delete_campaign(campaign_id: str, tenant_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM campaigns WHERE id = $1 AND tenant_id = $2", campaign_id, tenant_id)
        return not res.endswith("0")


_CAMPAIGN_UPDATABLE = {"name", "agent_id", "status", "schedule", "total_contacts", "called", "booked", "failed"}

async def db_update_campaign_fields(campaign_id: str, **fields) -> bool:
    safe_fields = {k: v for k, v in fields.items() if k in _CAMPAIGN_UPDATABLE}
    if not safe_fields:
        return False
        
    sets = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(safe_fields.keys()))
    vals = list(safe_fields.values())
    vals.append(campaign_id)
    
    query = f"UPDATE campaigns SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ${len(vals)}"
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(query, *vals)
        return res.endswith("1")


# ── Contact CRUD ─────────────────────────────────────────────────────

async def db_save_contacts(campaign_id: str, contacts: list[dict]) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM contacts WHERE campaign_id = $1", campaign_id)
            
            # Use executemany for bulk insert
            records = []
            for c in contacts:
                extra = c.get("extra", {})
                if isinstance(extra, dict):
                    extra = json.dumps(extra)
                records.append((campaign_id, c["phone"], c.get("name", ""), c.get("status", "pending"), extra))
                
            await conn.executemany(
                "INSERT INTO contacts (campaign_id, phone, name, status, extra) VALUES ($1, $2, $3, $4, $5)",
                records
            )
            return len(contacts)


async def db_get_contacts(campaign_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM contacts WHERE campaign_id = $1 ORDER BY id", campaign_id)
        results = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("extra"), str):
                try: d["extra"] = json.loads(d["extra"])
                except (json.JSONDecodeError, TypeError, ValueError): pass
            if "created_at" in d and hasattr(d["created_at"], "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            results.append(d)
        return results


_CONTACT_UPDATABLE = {"phone", "name", "status", "extra", "call_sid", "attempt", "outcome"}

async def db_update_contact(contact_id: int, **fields) -> bool:
    safe_fields = {k: v for k, v in fields.items() if k in _CONTACT_UPDATABLE}
    if not safe_fields:
        return False
    if "extra" in safe_fields and isinstance(safe_fields["extra"], dict):
        safe_fields["extra"] = json.dumps(safe_fields["extra"])
        
    sets = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(safe_fields.keys()))
    vals = list(safe_fields.values())
    vals.append(contact_id)
    
    query = f"UPDATE contacts SET {sets} WHERE id = ${len(vals)}"
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(query, *vals)
        return res.endswith("1")


async def db_update_contact_by_index(campaign_id: str, index: int, **fields) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        # PostgreSQL OFFSET requires LIMIT
        row = await conn.fetchrow(
            "SELECT id FROM contacts WHERE campaign_id = $1 ORDER BY id LIMIT 1 OFFSET $2",
            campaign_id, index
        )
        if not row:
            return False
        return await db_update_contact(row["id"], **fields)


# ── Call CRUD ────────────────────────────────────────────────────────

async def db_persist_call(call_log: dict, tenant_id: str):
    query = """
        INSERT INTO calls
           (call_id, tenant_id, agent_id, business_type, started_at, ended_at,
            duration_seconds, outcome, outcome_detail, states_visited, hang_up_state,
            state_transitions, total_turns, frustration_triggered, escalation_triggered,
            repeat_detected, tools_used, cost_per_minute, cost_estimate, transcript)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
        ON CONFLICT (call_id) DO UPDATE SET
            outcome = EXCLUDED.outcome,
            ended_at = EXCLUDED.ended_at,
            duration_seconds = EXCLUDED.duration_seconds
    """
    
    # Parse python datetimes for asyncpg if available
    try:
        started_at = datetime.fromisoformat(call_log["started_at"]) if call_log.get("started_at") else None
    except (ValueError, TypeError): started_at = None
    
    try:
        ended_at = datetime.fromisoformat(call_log["ended_at"]) if call_log.get("ended_at") else None
    except (ValueError, TypeError): ended_at = None
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                query,
                call_log["call_id"], tenant_id, call_log["agent_id"],
                call_log.get("business_type", ""),
                started_at, ended_at,
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
                json.dumps(call_log.get("transcript", []))
            )
        except Exception as e:
            logger.error(f"Failed to persist call {call_log.get('call_id')}: {e}")


def _call_row_to_dict(row: asyncpg.Record) -> dict:
    d = dict(row)
    for key in ("states_visited", "state_transitions", "tools_used", "transcript"):
        if isinstance(d.get(key), str):
            try: d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError, ValueError): pass
    d["frustration_triggered"] = bool(d.get("frustration_triggered", 0))
    d["escalation_triggered"] = bool(d.get("escalation_triggered", 0))
    d["repeat_detected"] = bool(d.get("repeat_detected", 0))
    
    # Cast dates
    for key in ("started_at", "ended_at", "created_at"):
        if key in d and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat()
            
    return d


async def db_get_calls(tenant_id: str, days: int = 7, agent_id: str = None,
                       business_type: str = None) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=days)
    
    query = "SELECT * FROM calls WHERE tenant_id = $1 AND started_at >= $2"
    params = [tenant_id, cutoff]
    
    if agent_id:
        params.append(agent_id)
        query += f" AND agent_id = ${len(params)}"
    if business_type:
        params.append(business_type)
        query += f" AND business_type = ${len(params)}"
        
    query += " ORDER BY started_at DESC"
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [_call_row_to_dict(r) for r in rows]


async def db_clear_analytics(tenant_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute("DELETE FROM calls WHERE tenant_id = $1", tenant_id)
            return True
        except Exception as e:
            logger.error(f"Failed to clear analytics for {tenant_id}: {e}")
            return False


async def db_get_analytics(tenant_id: str, days: int = 30) -> dict:
    # (Leaving original logic mostly intact, but swapping executor calls)
    cutoff = datetime.now() - timedelta(days=days)
    prev_cutoff = datetime.now() - timedelta(days=days * 2)

    pool = await get_pool()
    async with pool.acquire() as conn:
        c_rows = await conn.fetch(
            "SELECT * FROM calls WHERE tenant_id = $1 AND started_at >= $2 ORDER BY started_at DESC", 
            tenant_id, cutoff
        )
        current_calls = [_call_row_to_dict(r) for r in c_rows]

        p_rows = await conn.fetch(
            "SELECT * FROM calls WHERE tenant_id = $1 AND started_at >= $2 AND started_at < $3", 
            tenant_id, prev_cutoff, cutoff
        )
        previous_calls = [_call_row_to_dict(r) for r in p_rows]

    # ... The rest of the analytics aggregation is pure python list math
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
        if c.get("started_at"):
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
        "recent_calls": current_calls[:10],
    }


# ── Lead CRUD ────────────────────────────────────────────────────────

async def db_log_lead(lead: dict, tenant_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """INSERT INTO leads (tenant_id, type, name, phone, interest, notes, priority, date, time, reason, confirmation)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
                tenant_id, lead.get("type", "lead"), lead.get("name", ""),
                lead.get("phone", ""), lead.get("interest", ""),
                lead.get("notes", ""), lead.get("priority", "medium"),
                lead.get("date", ""), lead.get("time", ""),
                lead.get("reason", ""), lead.get("confirmation", "")
            )
        except Exception as e:
            logger.error(f"Failed to log lead: {e}")


async def db_lookup_client(phone: str, tenant_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM leads WHERE tenant_id = $1 AND phone = $2 ORDER BY created_at DESC LIMIT 1",
            tenant_id, phone
        )
        return dict(row) if row else None


# ── Webhooks & Integrations ─────────────────────────────────────────

async def db_generate_api_key(tenant_id: str) -> str:
    """Generate a new secure API key for a tenant and save it. Returns the cleartext key."""
    import secrets
    # Generate a secure 32-byte token, base64url encoded
    raw_token = secrets.token_urlsafe(32)
    api_key = f"sk_live_{raw_token}"
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tenants SET api_key = $1 WHERE id = $2", api_key, tenant_id)
        
    return api_key
