# Superactive — Production TODO

## Phase 1: Security ✅

- [x] `tool_registry.py` — Per-call closures replacing global state (race condition fix)
- [x] `routes/monitor.py` — JWT auth on WebSocket connect (`?token=` param)
- [x] `live_monitor.py` — Tenant-scoped broadcasts
- [x] `call_logger.py` — Public `get_active_call()` + tenant_id on all emits
- [x] `routes/telephony.py` — `xml_escape()` on TwiML `ws_host`
- [x] `server.py` + `routes/auth.py` — Rate limiting (5/min login, 10/hr register)
- [x] `db.py` — Column whitelists on all dynamic UPDATEs
- [x] `routes/auth.py` — Password minimum 12 chars
- [x] `db.py` — Random default admin password (printed to logs)
- [x] `.gitignore` — Exclude `*.db`, removed `superactive.db` from tracking
- [ ] JWT cookie — Set HttpOnly/Secure/SameSite (requires refactoring cookie flow)

---

## Phase 2: Reliability ✅

- [x] `useCallMonitor.ts` — Dynamic URLs from `API_BASE_URL`, JWT on WS, exponential backoff reconnect
- [x] `Sidebar.tsx` — `API_BASE_URL` import, dark theme user profile
- [x] `db.py` — `PRAGMA busy_timeout=5000`
- [x] `ErrorBoundary.tsx` — Created + wrapped in dashboard layout

---

## Phase 3: Testing ✅

- [x] 38 tests passing: `test_auth.py` (10), `test_state_machine.py` (13), `test_tool_registry.py` (8)
- [ ] `test_db.py` — CRUD, tenant isolation
- [ ] Integration tests: auth flow, agent CRUD, campaign lifecycle

---

## Phase 4: Frontend Polish ✅

- [x] `agents/page.tsx` — Converted inline styles → Tailwind
- [x] `monitor/page.tsx` — Replaced fake CRM data with real call info, removed decorative buttons
- [x] `Sidebar.tsx` — Dark theme user profile fix

---

## Phase 5: Code Cleanup ✅

- [x] `state_machine.py` — Removed dead memory injection code
- [x] `routes/telephony.py` — `import asyncio` moved to top
- [x] `tool_registry.py` — Fixed `"interneally"` typo
- [x] `requirements.txt` — Added `slowapi`

---

## Phase 6: Infrastructure ✅

- [x] `routes/health.py` — `GET /health` with DB connectivity check
- [x] `Dockerfile` — Python 3.12-slim, HEALTHCHECK directive
- [x] `dashboard/Dockerfile` — Multi-stage Node 20 Alpine build
- [x] `docker-compose.yml` — Backend + dashboard, health-based depends_on
- [x] `.dockerignore` — Backend + dashboard

---

## Remaining (Future)

- [ ] HttpOnly JWT cookie flow
- [ ] CI/CD pipeline (`.github/workflows/test.yml`)
- [ ] PostgreSQL migration
- [ ] Sentry error tracking
- [ ] Per-tenant Twilio credentials
- [ ] Stripe billing
- [ ] Accessibility (ARIA labels, keyboard nav)
