# V2 Shows Module Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Shows module ownership, restore Today create behavior, and eliminate duplicate Shows refreshes while preserving compatibility.

**Architecture:** The Shows feature owns its page data, form, domain helpers, and API calls. App keeps only a cross-domain Shows snapshot for Today/Calendar and receives updated snapshots from the feature rather than reloading every collection after each Shows mutation. Backend compatibility layers remain only where existing callers require them.

**Tech Stack:** Vue 3 + TypeScript, FastAPI, SQLite, GitHub Actions Docker E2E

**Spec:** `docs/superpowers/specs/2026-09-17-v2-shows-module-cleanup-design.md`

## Global Constraints
- No public API or database changes.
- Preserve metadata and poster behavior.
- Preserve import/export compatibility.
- Do not deploy NAS.
- Use implementation-first concentrated verification; do not intentionally create failing CI commits solely for RED.

---

### Task 1: Make Shows frontend files physically feature-owned

**Files:**
- Modify: `frontend/src/features/shows/domain.ts`
- Modify: `frontend/src/features/shows/ShowForm.vue`
- Modify: `frontend/src/features/shows/api.ts` if needed
- Remove after dependency verification: `frontend/src/shows.ts`, `frontend/src/components/ShowForm.vue`, legacy root Shows view/card files

- [ ] Move domain helper/type implementations into feature domain.
- [ ] Move form implementation into feature directory and switch metadata/poster calls to feature API.
- [ ] Search repository for legacy imports and remove only dead duplicate files.
- [ ] Commit the coherent frontend ownership change.

### Task 2: Restore Today create UX and remove duplicate refresh

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/features/shows/ShowsView.vue`
- Modify: `frontend/src/features/shows/useShows.ts` if needed
- Test: existing frontend tests plus targeted tests where practical

- [ ] Add a one-shot create request from App to ShowsView when Today requests a Shows create.
- [ ] Make ShowsView open its create form when that request is received.
- [ ] Emit the current Shows snapshot after successful mutation instead of a generic global refresh.
- [ ] Update `records.shows` in App from that snapshot; do not call global `load()` for Shows mutations.
- [ ] Preserve notices, errors, filters, stats rendering, and page-local reload behavior.
- [ ] Commit the interaction/refresh cleanup.

### Task 3: Audit backend compatibility residue

**Files:**
- Inspect/modify only if justified: `backend/app/records.py`, `backend/app/schemas.py`, `backend/app/metadata.py`, `backend/app/imports.py`
- Test: backend Shows/schema/metadata/import tests

- [ ] Search remaining Shows references and classify runtime ownership vs compatibility.
- [ ] Remove only dead residue; keep required facades and imports.
- [ ] Clean trivial domain-local style residue if safe.
- [ ] Commit only if code changes are warranted.

### Task 4: Verify, review, and integrate

- [ ] Run feature-branch GitHub CI and require frontend, backend, and Docker E2E success.
- [ ] Review final diff for dead imports, duplicated implementation, import cycles, and UX regressions.
- [ ] Open PR to `main` with exact verification evidence.
- [ ] Require PR CI green, then merge under standing authorization.
- [ ] Verify `main` CI is fully green before declaring Phase 4 complete.
