# Digital Life V2 Modular Architecture Design

## Goal

Evolve Digital Life from a small monolith into a modular monolith without changing its deployment model, database, public behavior, or NAS ownership. Remove the two current scaling bottlenecks: the frontend `App.vue` acting as global data/controller hub and backend `records.py` accumulating domain-specific behavior.

## Constraints

- Keep FastAPI + Vue 3 + TypeScript + SQLite + Docker Compose.
- Keep one backend service and one database; no microservices.
- Keep Alembic as the single migration chain.
- Preserve existing API behavior and user-visible behavior during the refactor.
- NAS deployment remains user-operated.
- Development workflow changes to: implement -> focused/local-or-CI tests -> full CI Docker/E2E validation -> merge. RED-first/TDD is not mandatory for routine work; targeted regression tests remain required for risky bugs, migrations, concurrency, or behavior changes.
- Avoid a big-bang rewrite. Move one domain at a time.

## Frontend Architecture

`App.vue` becomes the application shell. It owns session/bootstrap, navigation, theme, global error/notice presentation, and page composition. It should no longer own every domain's CRUD and refresh behavior.

Create feature-oriented modules under `frontend/src/features/`. The first migrated domain is Shows because it already has dedicated UI and richer business behavior. A feature owns its API calls, domain helpers, UI components, page-level loading/busy/error state, and refresh after mutations. Shared session/API primitives remain outside features.

Initial target:

```text
frontend/src/
  app/
    useSession.ts
  features/
    shows/
      api.ts
      domain.ts
      ShowCard.vue
      ShowForm.vue
      ShowsView.vue
  shared/
  App.vue
```

The refactor may preserve existing `views/` and `components/` for domains not yet migrated. No requirement exists to move every module in V2 phase 1.

### Data Loading

Stop treating the entire `Records` object as the mandatory refresh unit. Shows becomes independently loaded and refreshed. A show create/edit/advance operation refreshes Shows only. Other existing modules may continue using the legacy aggregate loader until migrated.

Cross-domain pages such as Today/Calendar remain compatible during phase 1. If they need Shows, App may retain a lightweight shared snapshot temporarily; feature ownership must expose an explicit refresh/update boundary rather than reintroducing a global full reload.

Longer term, cross-domain pages should use purpose-built aggregate endpoints rather than downloading every domain's full record set solely for composition.

## Backend Architecture

Extract Shows from generic `records.py` into a dedicated backend package while keeping URLs and response schemas compatible.

Target:

```text
backend/app/
  shows/
    __init__.py
    router.py
    service.py
    schemas.py
    metadata.py
  records.py
```

`router.py` owns `/api/shows`, `/api/shows/{id}`, `/advance`, poster and metadata routes as applicable. `service.py` owns completion-date transitions, ownership-aware show operations, and other show business rules. `schemas.py` owns Show request/response schemas. `metadata.py` owns Bangumi/TMDB scraping logic.

Generic `records.py` keeps genuinely simple collections. Other domains are extracted only when their behavior justifies it.

Models remain in the existing shared SQLAlchemy model layer for now. Alembic remains global. This avoids introducing repository/unit-of-work abstractions that the current application does not need.

## Compatibility and Data

This phase is primarily structural. Existing SQLite rows require no rewrite. Existing Shows endpoints retain their URLs and JSON semantics. Import/export remains compatible. Existing completion-date timezone semantics, metadata canonical URLs, poster handling, and media-type behavior must remain unchanged.

## Error Handling

Feature modules surface domain errors to the App-level global error/notice mechanism or their local form error state. Authentication expiry remains globally handled. Backend domain routers continue to use the existing authentication/ownership primitives and HTTP status semantics.

## Verification Workflow

Routine work does not require an intentional RED run. Each implementation batch must instead end with focused tests/builds appropriate to the touched code. Before merge, GitHub CI must run backend lint/tests, frontend tests/build, Docker deployment behavior checks, and Playwright E2E. Any migration or high-risk behavioral fix gets a targeted regression test even without RED-first execution.

The feature branch is merged only after CI is green. After merge, main CI is verified. NAS deployment is not performed by the assistant.

## Phase 1 Success Criteria

- `App.vue` no longer performs Shows CRUD/advance by routing through the global `load()` cycle.
- Shows frontend code lives behind a coherent feature boundary.
- Shows backend endpoints and business logic no longer live in generic `records.py`/top-level metadata routing.
- Existing Shows behavior and API compatibility are preserved.
- Existing non-Shows modules continue to work without a forced rewrite.
- Full GitHub CI including Docker E2E is green.
