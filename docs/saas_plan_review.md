# SaaS Foundation Plan Review
**Date:** February 2026
**Status:** ✅ Validated with minor recommendations

## 1. Overall Assessment
The plan provided is **technically sound, comprehensive, and perfectly aligned** with the "minimal tooling" constraint. It correctly identifies the critical path (DB -> Auth -> Routing -> Dashboard) without introducing unnecessary complexity like Docker or Kubernetes.

## 2. Dependencies Check
*   **PyJWT:** ✅ Installed.
*   **Aiosqlite:** ❌ Missing. Must be added to `requirements.txt`.
*   **Passlib/Bcrypt:** Recommended for secure password hashing. The plan mentions `hashlib` (standard lib) which is acceptable for an MVP but `bcrypt` is the industry standard for production.

## 3. Critical Architecture Notes

### A. The "Circular Import" Trap
*   **Risk:** `agent_config.py` (Models) <-> `db.py` (CRUD).
*   **Fix:** Ensure `db.py` **NEVER** imports from `agent_config.py`.
    *   `db.py` should return raw `dict` or `sqlite3.Row` objects.
    *   `agent_config.py` should import `db`, call the functions, and validate the raw data into Pydantic models.

### B. The `agent_id` Collision Issue (Telephony)
*   **Context:** `routes/telephony.py` uses `/incoming-call?agent_id=X`.
*   **Risk:** If Tenant A and Tenant B both name their agent "receptionist", the system can't tell them apart if `agent_id` is just a slug.
*   **Plan Statement:** "Agent id stays as human-readable slug but gets tenant_id prefix in uniqueness".
*   **Recommendation:** The `agents` table Primary Key `id` MUST be globally unique.
    *   *Option A:* Enforce random UUIDs for `id` (e.g. `550e8400-e29b...`).
    *   *Option B:* Dashboard automatically prepends tenant name (e.g. `acme_receptionist`).
    *   *Recommendation:* Use **UUIDs** for the internal `id` (primary key) and add a `slug` column for the human-readable name ("receptionist"). The webhook should use the UUID `id`.

### C. Migration Strategy
*   **Function:** `migrate_from_files()`
*   **Safety:** This function must be chemically pure — it should only run if the `tenants` table is empty. If run twice, it should do nothing.

## 4. Verification Plan (Additions)
The plan lists good verification steps. I would add:
1.  **Concurrency Test:** Create 2 simultaneous calls to different tenants to ensure `get_current_agent` doesn't cross-contaminate memory (since `agent_config` won't be a global singleton anymore).
2.  **Auth Guard:** Try to access `/api/agents` with a valid JWT from *Tenant A* and try to read *Tenant B's* agent ID. (Should return 404 or empty list).

## 5. Verdict
**Proceed.** The plan is actionable and low-risk.
