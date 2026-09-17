# V2 Backend Shows Boundary Design

## Goal

Complete the backend Shows extraction so Shows schemas and metadata logic physically live under `backend/app/shows/` while preserving all existing APIs, request/response shapes, database behavior, and compatibility imports.

## Constraints

- Keep the modular monolith architecture; do not introduce microservices.
- Keep SQLite and the existing Alembic/global database setup unchanged.
- Do not change `/api/shows` routes, payloads, response models, status codes, or metadata provider behavior.
- Do not change Bangumi/TMDB lookup semantics, poster caching/upload behavior, environment variables, or stored data format.
- Preserve compatibility for existing imports from `app.schemas` and `app.metadata` during the migration.
- Preserve test monkeypatch compatibility for callers that patch `app.metadata` symbols.
- Do not deploy the NAS.

## Target structure

```text
backend/app/
  shows/
    __init__.py
    router.py
    service.py
    schemas.py
    metadata.py
  schemas.py       # compatibility exports for Shows names
  metadata.py      # compatibility facade for historical import/patch points
```

## Schema boundary

`app.shows.schemas` becomes the source of truth for Shows-specific schema definitions: `MAX_EPISODES`, `ShowPayload`, `ShowView`, and `ShowPatch`. Shared primitives that remain genuinely global (`Payload`, `ResourceId`, `ISODate`, `Notes`, `StrictInt`, `patch_schema`) stay in `app.schemas` and are imported by the Shows schema module.

To avoid a circular import, `app.schemas` must define the shared primitives first, import the Shows schema types only after those primitives exist, and then continue defining non-Shows schemas. Existing imports such as `from app.schemas import ShowPayload` remain valid through re-exported imports.

## Metadata boundary

The implementation for metadata search and poster handling moves to `app.shows.metadata`. Runtime route registration should use the Shows-domain implementation.

`app.metadata` remains as a compatibility facade. It should expose the same public constants/functions/router-facing symbols used by tests and legacy imports. Compatibility must be implemented carefully so existing monkeypatches against `app.metadata` still affect the behavior exercised by compatibility tests; where necessary, wrappers delegate through symbols in the facade rather than replacing it with a bare star-import.

## Router/service dependencies

Shows routing and Shows-domain modules should prefer `app.shows.schemas`, `app.shows.service`, and `app.shows.metadata`. Generic `records.py` must not regain Shows CRUD ownership.

## Verification

Validation is concentrated rather than intentionally forcing RED commits:

1. backend lint and tests,
2. frontend tests/build to catch API/type regressions,
3. Docker E2E desktop/mobile workflows,
4. branch diff review for accidental API/data/UX changes,
5. PR CI green, merge to `main`, then main CI green.

No NAS deployment is performed by this phase.
