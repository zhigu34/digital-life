# V2 Frontend Shows Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Shows page data and mutation ownership out of `App.vue` into the Shows feature while preserving existing user-visible behavior and cross-domain compatibility.

**Architecture:** Keep `App.vue` as the application shell and retain the shared `records.shows` snapshot temporarily for Today/Calendar compatibility. A new Shows composable owns page-local list/loading/mutation state and uses the existing feature API boundary. The Shows view becomes the feature integration point; global refresh remains available only as a compatibility callback after successful mutations.

**Tech Stack:** Vue 3 Composition API, TypeScript, existing `api.ts`, Vitest/build, Playwright Docker E2E.

**Spec:** `docs/superpowers/specs/2026-09-17-v2-modular-architecture-design.md`

## File structure

- `frontend/src/features/shows/useShows.ts` — page-local Shows state, loading, create/update/delete/advance operations.
- `frontend/src/features/shows/domain.ts` — compatibility boundary for Shows-specific filtering/grouping/types currently in `src/shows.ts`.
- `frontend/src/features/shows/ShowsView.vue` — feature-owned view and orchestration.
- `frontend/src/features/shows/ShowCard.vue` — feature-owned card component.
- `frontend/src/features/shows/ShowForm.vue` — feature-owned form component.
- `frontend/src/App.vue` — remove direct Shows mutation/form ownership; retain temporary shared snapshot for aggregate pages.
- Existing root `views/components/shows.ts` paths may remain as compatibility wrappers until downstream imports are migrated.

## Task 1: Establish feature-local domain and component boundaries

- [ ] Add `features/shows/domain.ts` re-exporting/moving Shows-specific domain helpers.
- [ ] Move or wrap `ShowCard.vue`, `ShowForm.vue`, and `ShowsView.vue` under `features/shows` without behavior changes.
- [ ] Update internal imports to use feature-local paths.
- [ ] Run frontend tests/build through CI checkpoint.
- [ ] Commit the boundary change.

## Task 2: Add page-local Shows state ownership

- [ ] Add `useShows.ts` with `shows`, `loading`, `busy`, `error`, and explicit `load/create/update/delete/advance` methods backed by `features/shows/api.ts`.
- [ ] Protect async loads from stale account/page results where necessary.
- [ ] Keep errors compatible with the existing global 401/session handling contract.
- [ ] Add focused tests where existing frontend test structure supports composables; otherwise rely on component/build/E2E coverage.
- [ ] Commit the state ownership change.

## Task 3: Remove direct Shows CRUD ownership from App.vue

- [ ] Import the feature-owned `ShowsView` and `ShowForm` paths.
- [ ] Stop routing Shows create/edit/advance through generic `open/save/action` paths.
- [ ] Let Shows page load its own records when active.
- [ ] After successful Shows mutations, refresh the temporary shared aggregate snapshot so Today/Calendar/Stats remain current.
- [ ] Preserve existing notices, confirmation behavior, session-expiry handling, and modal UX.
- [ ] Commit the shell reduction.

## Task 4: Verify regression behavior

- [ ] Verify frontend unit tests and production build.
- [ ] Verify backend suite remains green.
- [ ] Verify Docker E2E desktop/mobile workflows.
- [ ] Review the branch diff for accidental API/data/UX changes.
- [ ] Fix any CI regressions using systematic debugging.

## Task 5: Integrate

- [ ] Open a PR from `codex/v2-frontend-shows-ownership` to `main`.
- [ ] Confirm all PR/branch CI jobs are green.
- [ ] Merge to `main` under the standing authorization.
- [ ] Confirm `main` CI is green.
- [ ] Do not deploy the NAS.
