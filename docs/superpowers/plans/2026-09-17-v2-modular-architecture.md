# Digital Life V2 Modular Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the current small monolith into a modular monolith by extracting Shows into explicit frontend/backend feature boundaries and removing Shows mutations from the global App reload cycle.

**Architecture:** Preserve one FastAPI backend, one Vue SPA, and one SQLite database. Extract only the already-complex Shows domain first; keep simpler collections on the legacy path and preserve API/user behavior.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Alembic, Vue 3, TypeScript, Vitest, Playwright, Docker Compose, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-17-v2-modular-architecture-design.md`

## Global Constraints

- Keep FastAPI + Vue 3 + TypeScript + SQLite + Docker Compose.
- No microservices and no database replacement.
- Preserve existing Shows endpoint URLs and JSON semantics.
- Preserve import/export and cross-domain page behavior.
- NAS deployment remains user-operated.
- Workflow is implement -> focused tests/build -> full GitHub CI Docker/E2E -> merge; routine tasks do not require an intentional RED run.
- Add targeted regression tests for behavior changes or high-risk logic.

---

### Task 1: Extract Backend Shows Domain

**Files:**
- Create: `backend/app/shows/__init__.py`
- Create: `backend/app/shows/router.py`
- Create: `backend/app/shows/service.py`
- Create: `backend/app/shows/schemas.py`
- Create: `backend/app/shows/metadata.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/records.py`
- Modify: `backend/app/metadata.py` or remove it after imports are migrated
- Modify: `backend/app/schemas.py`
- Test: existing `backend/tests/test_records.py`, `backend/tests/test_metadata.py`, poster/API tests

**Interfaces:**
- Produces `app.shows.router.router` mounted by `main.py`.
- Keeps `/api/shows`, `/api/shows/{id}`, `/api/shows/{id}/advance`, metadata and poster URLs compatible.
- `service.py` owns show ownership lookup, create/update/delete/advance and completion-date transition behavior.
- Shared auth/database/model primitives remain shared.

- [ ] Move Show schemas into the feature package while preserving imports needed by export/import code.
- [ ] Move metadata implementation behind `app.shows.metadata` without changing Bangumi/TMDB result semantics.
- [ ] Move Show CRUD/advance/poster/metadata routing to the Shows router.
- [ ] Remove Show-specific branches and collection registration from generic `records.py`.
- [ ] Update `main.py` router registration order so metadata/static show routes remain ahead of dynamic `{item_id}` matching.
- [ ] Run backend verification: `cd backend && uv run ruff check . && uv run pytest`.
- [ ] Commit backend extraction as one independently reviewable change.

### Task 2: Establish Frontend Shows Feature Boundary

**Files:**
- Create: `frontend/src/features/shows/api.ts`
- Create: `frontend/src/features/shows/domain.ts`
- Move/refactor: `frontend/src/shows.ts`
- Move/refactor: `frontend/src/components/ShowCard.vue`
- Move/refactor: `frontend/src/components/ShowForm.vue`
- Move/refactor: `frontend/src/views/ShowsView.vue`
- Modify imports in `frontend/src/App.vue` and tests

**Interfaces:**
- `api.ts` exposes list/create/update/delete/advance and metadata/poster operations using the existing shared `api()` client.
- `domain.ts` owns normalize/filter/group/metadata-patch helpers.
- `ShowsView.vue` is the page-level feature entry point.

- [ ] Create the feature directory and move Shows-only domain helpers behind it.
- [ ] Move Shows-only components/view and update imports without changing rendered behavior.
- [ ] Add/adjust unit tests for moved helpers and component imports where necessary.
- [ ] Run `cd frontend && npm test && npm run build`.
- [ ] Commit the feature-boundary move separately from behavior changes.

### Task 3: Give Shows Independent Data and Mutation Ownership

**Files:**
- Modify: `frontend/src/features/shows/ShowsView.vue`
- Modify: `frontend/src/features/shows/api.ts`
- Modify: `frontend/src/App.vue`
- Modify/create focused frontend tests
- Modify E2E only where needed to assert refresh isolation

**Interfaces:**
- `ShowsView` loads its own list on entry/mount and refreshes only Shows after create/edit/advance/delete.
- App supplies global session/error/notice hooks but does not perform Shows CRUD.
- Authentication expiry continues through the shared API/session path.

- [ ] Move Shows list loading from the global `load()` path into the Shows feature.
- [ ] Move create/update/delete/advance orchestration into the Shows feature.
- [ ] Keep form busy/error and global notification behavior equivalent.
- [ ] Preserve Today/Calendar compatibility using the smallest temporary shared snapshot boundary needed; do not restore global full refreshes.
- [ ] Verify a Shows mutation does not trigger requests for unrelated collections with a focused frontend or E2E assertion.
- [ ] Run frontend tests/build and the relevant Playwright Shows spec.
- [ ] Commit independent Shows ownership.

### Task 4: Reduce App Shell Responsibilities Safely

**Files:**
- Create: `frontend/src/app/useSession.ts` if session extraction materially simplifies App
- Modify: `frontend/src/App.vue`
- Modify shared type/API files only as needed
- Test existing frontend unit/E2E suite

**Interfaces:**
- App remains responsible for shell/navigation/theme/global notifications.
- Session/bootstrap may move to `useSession.ts`; domain CRUD must not move into it.

- [ ] Extract session/bootstrap helpers only if it reduces App responsibility without introducing a new global god-composable.
- [ ] Remove dead Shows-specific handlers/state/imports from App.
- [ ] Confirm legacy modules continue using their existing paths unchanged.
- [ ] Run `cd frontend && npm test && npm run build`.
- [ ] Commit App-shell cleanup.

### Task 5: Full Regression, Review, and Merge

**Files:**
- Modify: `HANDOFF.md` and/or architecture documentation if present
- Modify tests only for defects found during verification

**Interfaces:**
- No new user-facing API contract.
- Branch must be merge-ready with full CI green.

- [ ] Review `main...codex/v2-modular-architecture` for accidental behavior changes, duplicate compatibility layers, or cross-domain coupling.
- [ ] Push branch and run full GitHub CI: backend lint/tests, frontend tests/build, deployment checks, Docker E2E.
- [ ] If CI exposes a defect, diagnose root cause, fix it, and rerun the affected/full validation; do not add ceremonial RED runs.
- [ ] Update handoff/architecture notes with the new module boundaries and workflow.
- [ ] Open PR and review the final diff.
- [ ] After all feature-branch CI checks are green, merge to `main` under standing authorization.
- [ ] Verify the resulting `main` CI is green.
- [ ] Do not deploy to NAS; leave NAS deployment to the user.
