# Superactive — Production TODO

## Backend & Infrastructure

### Phase 1: Security ✅
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
- [x] JWT cookie — Set HttpOnly/Secure/SameSite (requires refactoring cookie flow)

---

### Phase 2: Reliability ✅
- [x] `useCallMonitor.ts` — Dynamic URLs from `API_BASE_URL`, JWT on WS, exponential backoff reconnect
- [x] `Sidebar.tsx` — `API_BASE_URL` import, dark theme user profile
- [x] `db.py` — `PRAGMA busy_timeout=5000`
- [x] `ErrorBoundary.tsx` — Created + wrapped in dashboard layout

---

### Phase 3: Testing ✅
- [x] 49 tests passing: `test_auth.py` (12), `test_state_machine.py` (13), `test_tool_registry.py` (8), `test_jwt_cookie.py` (16)
- [x] `test_db_postgres.py` — CRUD, tenant isolation (5 tests)
- [x] Integration tests: auth flow, agent CRUD, campaign lifecycle

---

### Phase 4: Frontend Polish (Initial) ✅
- [x] `agents/page.tsx` — Converted inline styles → Tailwind
- [x] `monitor/page.tsx` — Replaced fake CRM data with real call info, removed decorative buttons
- [x] `Sidebar.tsx` — Dark theme user profile fix

---

### Phase 5: Code Cleanup ✅
- [x] `state_machine.py` — Removed dead memory injection code
- [x] `routes/telephony.py` — `import asyncio` moved to top
- [x] `tool_registry.py` — Fixed `"interneally"` typo
- [x] `requirements.txt` — Added `slowapi`

---

### Phase 6: Infrastructure ✅
- [x] `routes/health.py` — `GET /health` with DB connectivity check
- [x] `Dockerfile` — Python 3.12-slim, HEALTHCHECK directive
- [x] `dashboard/Dockerfile` — Multi-stage Node 20 Alpine build
- [x] `docker-compose.yml` — Backend + dashboard, health-based depends_on
- [x] `.dockerignore` — Backend + dashboard

---

### Phase 7: Production Readiness (Scaling & Resiliency)
#### Proposed Architectural Changes
- [x] **1. Database Migration:** Migrate from `aiosqlite` to PostgreSQL using `asyncpg`.
- [x] **2. Resilient Message Queue (Campaign Dialer):** Replace in-memory `asyncio` loop with a durable worker queue (Redis + ARQ).
- [x] **3. Centralized Telemetry:** Implement OpenTelemetry natively mapped to Google Cloud Trace/Monitoring for pipeline frame lag, transcription latency, and STT failure rates instead of sequential DB logging.
- [x] **4. Robust WebSocket Sync:** Upgraded frontend/backend real-time sync to replace SWR polling for Live Monitor call takeover and active stats. Validated via robust integration testing.

#### Database & Redis Migration Status
- [x] **Step 1: Local Setup:** Multi-container docker-compose up running Postgres and Redis.
- [x] **Step 2: Database Refactor:** Asyncpg pools, parameterized queries, JSONB column types.
- [x] **Step 3: Worker Queue:** ARQ worker (`worker.py`) routing background tasks.
- [x] **Step 4: End-to-End Verification:** Upload CSV, Start Campaign, observe concurrent Postgres updates and worker stability.

---
---

## Dashboard Polish & Productization Roadmap

### Sprint 1: Kill the Embarrassments (Critical Fixes) ✅
- [x] Remove dead "Upgrade Plan" button — replaced with Quick Start guide
- [x] Remove dead "Live AI Support" card — replaced with Resources/docs links
- [x] Remove "Wipe History" debug button from main dashboard
- [x] Fix campaign ID generation — removed client-side Date.now()+Math.random(), let backend generate UUID
- [x] Replace all `alert()` and `console.error()` with toast notifications (sonner installed)
- [x] Replace all emoji icons with Lucide React icons (Sidebar, settings, campaigns, monitor)
- [x] Build validation: `npm run build` passed — all 10 pages compiled, 0 TypeScript errors

### Sprint 2: Styling Unification (Completed)
- [x] Convert campaigns page from inline styles → Tailwind (+ Lucide icons for Play/Pause/Plus/Upload/etc)
- [x] Convert settings page from inline styles → Tailwind (+ Lucide Phone/Globe/Cloud replacing emojis, removed 'Configured via .env')
- [x] Convert Sidebar from inline styles → Tailwind
- [x] Extract reusable components: `<Modal>`, `<PageHeader>`, `<EmptyState>`
- [x] Audit and remove unused CSS classes from `globals.css`
- [x] Build validation: `npm run build` passed — 10/10 pages, 0 errors

### Sprint 3: Onboarding & Empty States
- [ ] Add empty state with CTA to agents, campaigns, calls pages
- [ ] Add welcome banner on dashboard when 0 calls exist
- [ ] Create "Quick Start" card: Create Agent → Test Call → Go Live

### Sprint 4: Analytics Upgrade
- [ ] Add time-series call volume chart using `calls_per_day` data (already in API)
- [ ] Add cost tracking display (data exists in `AnalyticsData`)
- [ ] Add date range picker for analytics
- [ ] Display `hang_up_heatmap` data (already in API)

### Sprint 5: Settings & Integrations (SaaS Readiness)
- [ ] Make Twilio credentials editable in UI (fields exist in DB)
- [ ] Remove "Configured via .env" messaging
- [ ] Add per-tenant Twilio credential management

---

## Remaining (Future / Backlog)
- [x] HttpOnly JWT cookie flow
- [ ] CI/CD pipeline (`.github/workflows/test.yml`)
- [ ] Stripe billing integration
- [ ] Superactive Prospector (Google Maps scraper)
- [ ] Agent blueprint template library
- [ ] Mobile responsive layouts
- [ ] Call recording storage (S3/GCS)
- [ ] Accessibility (ARIA labels, keyboard nav)
