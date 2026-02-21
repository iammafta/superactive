# Superactive — Production TODO

## Phase 1: Security 🔴

### Concurrent Call Safety
- [x] `tool_registry.py` — Replace `_current_call_sid` / `_current_agent_config` globals with per-call closures in `register_tools_for_agent()`

### Monitor WebSocket Auth
- [x] `routes/monitor.py` — Validate JWT token on WebSocket connect (via `?token=` query param)
- [x] `live_monitor.py` — Track `tenant_id` per connection, filter broadcasts to same tenant only
- [x] `useCallMonitor.ts` — Send auth token in WS URL

### TwiML Injection
- [x] `routes/telephony.py` — Apply `xml_escape()` to `ws_host` in TwiML

### Rate Limiting
- [x] Install `slowapi`, add rate limits: `5/min` on `/login`, `10/hr` on `/register`

### Cookie Security
- [ ] Set JWT cookie server-side with `HttpOnly; Secure; SameSite=Strict` — deferred (requires backend cookie endpoint refactor)

### DB Input Validation
- [x] `db.py` — Whitelist allowed column names in `db_update_tenant()`, `db_update_campaign_fields()`, `db_update_contact()`

### Git Security
- [x] Remove `superactive.db` from git tracking
- [x] Add `*.db` to `.gitignore`
- [ ] Commit `.gitignore` change
- [ ] Verify no credentials were ever committed; rotate if so

---

## Phase 2: Reliability

### Hardcoded URLs
- [x] `useCallMonitor.ts` — Replace `ws://localhost:8765` and `http://localhost:8765` with dynamic URL from `API_BASE_URL`
- [x] `Sidebar.tsx` — Replace `http://localhost:8765/api/auth/me` with `API_BASE_URL`

### WebSocket Reconnection
- [x] `useCallMonitor.ts` — Add auto-reconnect with exponential backoff (1s→2s→4s→max 30s)

### SQLite Stability
- [x] `db.py` — Add `PRAGMA busy_timeout=5000` in `get_db()`

### Error Boundaries
- [x] Create `ErrorBoundary.tsx`, wrap pages in `(dashboard)/layout.tsx`

### Default Admin Password
- [x] `db.py` — Generate random password during migration instead of `"admin"`

### Password Minimum
- [x] `routes/auth.py` — Change minimum from 6 → 12 characters

---

## Phase 3: Testing

- [ ] Install `pytest`, `pytest-asyncio`, `httpx`
- [ ] Create `tests/` directory with `conftest.py` (in-memory SQLite fixture)
- [ ] `test_auth.py` — hash, verify, token create/decode, expired token, get_current_user
- [ ] `test_state_machine.py` — memory, repeat detection, frustration, limits, transitions
- [ ] `test_agent_config.py` — validation, build_full_prompt, guardrail levels
- [ ] `test_db.py` — CRUD for all entities, tenant isolation
- [ ] `test_tool_registry.py` — tool loading, definition/handler matching
- [ ] Integration: auth flow, agent CRUD, campaign lifecycle, call logging

---

## Phase 4: Frontend Polish

### Tailwind Transition
- [ ] Convert all inline `style={{}}` to Tailwind utility classes
- [ ] Convert `globals.css` custom classes (`.glass-card`, `.btn-*`, `.badge-*`, etc.) to `@apply` with Tailwind primitives
- [ ] Remove remaining CSS custom properties, use Tailwind theme

### Styling Fixes
- [x] `Sidebar.tsx` — Fix user profile section (light theme → dark theme)
- [ ] `agents/page.tsx` — Standardize on Tailwind (currently mixes inline + Tailwind + custom CSS)
- [ ] `monitor/page.tsx` — Wire or remove decorative Mute/Hold/Transfer buttons
- [ ] `monitor/page.tsx` — Replace fake `Customer 360` data with real caller info

### Accessibility
- [ ] Add ARIA labels to interactive elements
- [ ] Add keyboard navigation to sidebar and agent cards
- [ ] Add per-page `<title>` and `<meta description>`

---

## Phase 5: Code Cleanup

### Dead Code & Anti-patterns
- [x] `state_machine.py` — Remove commented-out memory injection block
- [x] `routes/telephony.py` — Move `import asyncio` from `finally` block to top
- [ ] `agent_config.py` — Move `import uuid` to top of file
- [x] `tool_registry.py:545` — Fix typo `"interneally"` → `"internally"`
- [ ] `live_monitor.py:17` — Fix typo `"subcribed"` → `"subscribed"` — already overwritten with clean file

### DRY
- [ ] Extract `_E164_RE` regex to shared `utils.py` (duplicated in telephony + campaigns)
- [ ] Consolidate Twilio client creation (duplicated in 3 files)

### Encapsulation
- [x] `call_logger.py` — Add public `get_active_call()` method
- [x] `routes/monitor.py` — Use it instead of accessing `_active_calls` directly

### Type Safety
- [ ] `lib/api.ts` — Replace `Record<string, unknown>` with typed interfaces
- [ ] `agents/page.tsx` — Type icon map and `Icon` prop properly

---

## Phase 6: Infrastructure

- [ ] Migrate SQLite → PostgreSQL (`db.py` internals, add `DATABASE_URL` env var)
- [ ] CI/CD: `.github/workflows/test.yml` (pytest + eslint on push)
- [ ] `Dockerfile` for backend + `dashboard/Dockerfile` for Next.js
- [ ] `docker-compose.yml` (backend + dashboard + Postgres)
- [ ] Health check endpoint `GET /health` with DB connectivity test
- [ ] Sentry error tracking
- [ ] Per-tenant Twilio credentials
- [ ] Stripe billing integration
