# V2 Shows Module Cleanup Design

## Goal
Finish the Shows modularization by making the feature directories the single implementation source, restoring Today-to-create UX, and removing duplicate refresh work without changing public API or persistence behavior.

## Frontend
- `frontend/src/features/shows/ShowForm.vue` becomes the physical form implementation and uses feature-local API/domain imports.
- `frontend/src/features/shows/domain.ts` becomes the physical source of Shows domain helpers and types.
- Legacy root Shows implementation files are removed only after repository-wide dependency checks confirm no runtime imports remain.
- `ShowsView` accepts a one-shot create request from the app shell so Today's “添加作品” navigates to Shows and opens the create modal.
- Shows mutations keep page-local state authoritative. Instead of asking App to perform its full global `load()`, the feature emits its current Shows snapshot after mutation; App updates only `records.shows` for Today/Calendar compatibility. This removes the duplicate `/shows` fetch while keeping aggregate views fresh.

## Backend
- Inspect `records.py`, `schemas.py`, and `metadata.py` for remaining Shows ownership.
- Keep compatibility facades/imports that still have callers (including import/export and metadata monkeypatch compatibility); remove only provably dead residue.
- No route, request/response schema, database, provider, or poster behavior changes.

## Verification
Use the existing repository CI as the authoritative environment: frontend tests/build, backend Ruff/pytest/deployment checks, and Docker E2E desktop/mobile/persistence/redeploy. Work on `codex/v2-shows-module-cleanup`, open a PR after feature CI is green, merge when PR CI is green, then verify main CI. NAS deployment is excluded.