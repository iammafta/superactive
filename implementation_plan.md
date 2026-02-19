# Implementation Plan - Phase 3 & 4: Logic Verification & Hardening

## Goal
We have successfully refactored the architecture (Tier 3) and established the core intelligence (Phase 2). The immediate goal is to **verify the business logic** (State Machine, Tools) and then move to **production hardening** (Auth, DB).

## Current Status
- **Phase 1 (Infra)**: ✅ Complete
- **Phase 2 (Intelligence)**: ✅ Complete (Voice/Brain connected)
- **Phase 3 (Refactor/Safety)**: ✅ Complete (Routes split, logging, safety checks)
- **Phase 3.5 (Logic Verification)**: ✅ Complete (Memory & Looping Fixes Deployed)

## Completed Items (From Legacy Plan)
### Tier 1 — Quick Wins (Safety & Code Quality) ✅
- [x] **Log Hygiene**: Replaced `print()` with `logger`.
- [x] **Security**: TwiML escaping for `agent_id`, `outbound`, `contact_name`.

### Tier 2 — Functional Fixes ✅
- [x] **VAD**: `SileroVADAnalyzer` wired into pipeline.
- [x] **Validation**: E.164 phone number validation in `routes/telephony.py`.

### Tier 3 — Architecture Refactor (The Split) ✅
- [x] **Modular Routes**: `server.py` split into `routes/agents.py`, `campaigns.py`, `calls.py`, `telephony.py`.
- [x] **Settings**: Settings endpoint created (though simple).

---

## Active Plan: Phase 3.5 — Logic Verification
*Immediate steps to prove the "Smart" features work before hardening.*

### 1. State Machine Verification
**Goal**: Ensure the AI transitions between `greeting`, `qualification`, and `booking` states correctly.
#### [VERIFY] `agents/insurance_qualifier.json`
- **Action**: Switch default agent to `insurance_qualifier` or pass `agent_id=insurance_qualifier` in webhook.
- **Test**: Call and say "I need auto insurance". Verify log shows `[TRANSITION: needs_analysis]`.

### 2. Tool Execution Test
**Goal**: Verify tools like `book_appointment` and `log_lead` actually trigger and log data.
#### [MODIFY] `tool_registry.py` (Completed in previous step)
- **Action**: Ensure `log_lead` writes to `data/leads.jsonl`.
- **Test**: Complete a flow that triggers `log_lead` and check the file.

---

## Upcoming: Phase 4 — Production Hardening
*To be executed after Logic Verification is confirmed.*

### Tier 4 — Authentication & Persistence
#### [NEW] Authentication
- **API Auth**: Implement `X-API-KEY` middleware for the dashboard API.
- **Multi-Tenancy**: Ensure logic supports multiple user accounts (if required).

#### [NEW] Database Migration
- **PostgreSQL/SQLite**: Migrate from `json` files (`agents/*.json`, `data/leads.jsonl`) to a proper database.
  - *Why*: JSON files verify logic but won't scale or handle concurrent writes well.

## Verification Checklist (Immediate)
- [ ] **State Machine**: Call transitions states correctly.
- [ ] **Tooling**: `log_lead` creates a record in `data/leads.jsonl`.
- [ ] **Outbound**: `campaign_dialer` successfully connects and speaks correct greeting.
