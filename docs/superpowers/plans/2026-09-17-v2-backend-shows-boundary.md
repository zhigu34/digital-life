# V2 Backend Shows Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `app.shows` the physical source of truth for Shows schemas and metadata while preserving compatibility imports and all existing behavior.

**Architecture:** Keep shared schema primitives in `app.schemas`, move Shows-specific models to `app.shows.schemas`, and keep `app.schemas` as a compatibility export surface. Move metadata implementation into `app.shows.metadata` while retaining `app.metadata` as a compatibility facade for legacy imports and monkeypatch points. Runtime Shows routing continues to expose the same `/api/shows` API.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy, httpx, SQLite, pytest/ruff, Vue/Vitest build, Docker/Playwright E2E.

**Spec:** `docs/superpowers/specs/2026-09-17-v2-backend-shows-boundary-design.md`

## Global Constraints

- Keep SQLite, Alembic, and modular-monolith deployment unchanged.
- Preserve existing `/api/shows` routes, request/response shapes, status codes, database model, and export/import compatibility.
- Preserve Bangumi/TMDB and poster behavior.
- Preserve `app.schemas` and `app.metadata` compatibility imports.
- Do not intentionally introduce failing RED commits; use focused tests and CI as regression gates.
- Do not deploy the NAS.

---

### Task 1: Move Shows schemas to the domain package

**Files:**
- Modify: `backend/app/shows/schemas.py`
- Modify: `backend/app/schemas.py`
- Inspect/Test: `backend/tests/`, `backend/app/imports.py`, `backend/app/shows/router.py`

**Interfaces:**
- Consumes shared primitives from `app.schemas`: `Payload`, `ResourceId`, `ISODate`, `Notes`, `StrictInt`, `patch_schema`.
- Produces `MAX_EPISODES`, `ShowPayload`, `ShowView`, `ShowPatch` from `app.shows.schemas`.
- Keeps `from app.schemas import ShowPayload, ShowView, ShowPatch` valid.

- [ ] Replace the current re-export-only `app.shows.schemas` with physical Shows schema definitions.
- [ ] Remove the physical Shows schema definitions from `app.schemas` and import/re-export the domain definitions after shared primitives are available.
- [ ] Update Shows-domain imports to prefer `app.shows.schemas` where appropriate.
- [ ] Verify import/export compatibility and focused backend tests.
- [ ] Commit the schema-boundary change.

### Task 2: Move metadata implementation into the Shows package

**Files:**
- Create: `backend/app/shows/metadata.py`
- Modify: `backend/app/metadata.py`
- Modify: `backend/app/main.py` or Shows router integration only if required for runtime route registration.
- Test: existing metadata/poster backend tests.

**Interfaces:**
- `app.shows.metadata` owns provider calls, validation, poster cache/upload logic, and the runtime metadata router.
- `app.metadata` remains a compatibility facade exposing historical functions/constants and test patch points.

- [ ] Copy/move the metadata implementation into `app.shows.metadata`, switching ownership lookup/schema imports to Shows-domain modules.
- [ ] Implement `app.metadata` as a compatibility facade rather than a second independent implementation.
- [ ] Preserve existing monkeypatch semantics used by tests.
- [ ] Ensure runtime registration does not duplicate routes.
- [ ] Run focused metadata/poster tests and backend lint/tests.
- [ ] Commit the metadata-boundary change.

### Task 3: Verify dependency direction and regressions

**Files:**
- Review: `backend/app/shows/*`, `backend/app/records.py`, `backend/app/main.py`, `backend/app/imports.py`, `backend/app/schemas.py`, `backend/app/metadata.py`

- [ ] Confirm generic `records.py` does not regain Shows CRUD ownership.
- [ ] Confirm `app.shows` is the implementation owner for Shows schemas and metadata.
- [ ] Confirm compatibility surfaces remain thin and documented.
- [ ] Run full backend CI-equivalent checks.
- [ ] Run frontend tests/build and Docker E2E through GitHub CI.
- [ ] Review the branch diff for accidental API/data/UX changes.

### Task 4: Integrate

- [ ] Open a PR from `codex/v2-backend-shows-boundary` to `main`.
- [ ] Confirm all branch/PR CI jobs are green.
- [ ] Merge under the standing authorization.
- [ ] Confirm `main` CI is green.
- [ ] Do not deploy the NAS.
