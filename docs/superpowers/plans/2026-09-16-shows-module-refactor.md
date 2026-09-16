# Shows Module Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the existing shows experience into focused `ShowsView`, `ShowCard`, and `ShowForm` modules without changing backend APIs, database schema, or user-visible behavior.

**Architecture:** Keep data fetching, mutation, notifications, and modal ownership in `App.vue`. Move pure shows filtering/progress/payload normalization into `src/shows.ts`, move list/card rendering into shows-specific Vue components, then remove all shows-only branches from the generic collection view/form. Existing `/api/shows`, metadata lookup, poster upload, and account isolation remain unchanged.

**Tech Stack:** Vue 3 + TypeScript, Vitest, Playwright, FastAPI/SQLite backend unchanged, GitHub Actions CI.

**Spec:** `docs/superpowers/specs/2026-09-16-shows-module-refactor-design.md`

## Global Constraints

- Do not add or modify Alembic migrations, `Show` database fields, or backend `/api/shows` contracts.
- Preserve Bangumi/TMDB lookup, poster proxy/upload, `local:upload`, status filtering, title search, edit-on-cover-click, and `advance` behavior.
- Preserve desktop compact horizontal cards and mobile single-column behavior using existing CSS classes where possible.
- `App.vue` remains the owner of API requests, busy/error state, deletion confirmation, and reload-after-mutation.
- No new runtime dependency; prefer pure helper tests plus existing Playwright coverage over adding a Vue component-test library.
- Execute with TDD: new production helpers are preceded by failing Vitest tests; behavior-preserving component extraction happens only after those characterization tests are green.

---

### Task 1: Extract testable shows domain helpers

**Files:**
- Create: `frontend/tests/shows.test.ts`
- Create: `frontend/src/shows.ts`

**Interfaces:**
- Produces: `ShowFilter`, `filterShows(shows, query, filter)`, `showProgressPercent(show)`, `showAdvanceDisabled(show, busy)`, `ShowFormDraft`, `normalizeShowPayload(draft)`.

- [ ] **Step 1: Write the failing tests** covering case-insensitive title search + status filtering, bounded progress percentage, advance-disabled semantics, numeric/nullable form normalization, and rejection when progress exceeds total.
- [ ] **Step 2: Run `cd frontend && npm test -- shows.test.ts`** and confirm RED because `../src/shows` does not exist.
- [ ] **Step 3: Implement the minimal helpers** with `Show` types from `src/types.ts`; `normalizeShowPayload` returns `{ data, error }` so form validation remains UI-agnostic.
- [ ] **Step 4: Run `cd frontend && npm test -- shows.test.ts && npm run build`** and confirm GREEN.
- [ ] **Step 5: Commit** with `test/feat: extract shows domain helpers` as appropriate to the red/green commits.

### Task 2: Extract the shows page and card

**Files:**
- Create: `frontend/src/components/ShowCard.vue`
- Create: `frontend/src/views/ShowsView.vue`
- Modify: `frontend/src/views/CollectionView.vue`
- Modify: `frontend/src/App.vue`
- Test: `frontend/e2e/workspace.spec.ts`

**Interfaces:**
- `ShowCard` props: `{ item: Show; busy: boolean }`; emits `edit(item: Show)` and `advance(id: number)`.
- `ShowsView` props: `{ shows: Show[]; stats: Stats | null; busy: boolean }`; emits `create`, `edit(item)`, and `action(id, "advance")`.
- Consumes Task 1 helpers for filtering and progress/disabled state.

- [ ] **Step 1: Extend Playwright characterization** so the shows flow explicitly verifies status filtering, title search, cover-click edit, progress advance, and completed-total disabled state on both configured viewports.
- [ ] **Step 2: Run the affected browser test in CI/baseline** and confirm existing behavior is green before refactor.
- [ ] **Step 3: Implement `ShowCard.vue`** by moving the current cover/metadata/progress markup unchanged in semantics.
- [ ] **Step 4: Implement `ShowsView.vue`** by moving shows page heading, stats, tabs, search, empty states, and list composition; use `filterShows`.
- [ ] **Step 5: Wire `App.vue`** so page `shows` renders `ShowsView`; generic collections render `CollectionView` only for tasks/expenses/milestones.
- [ ] **Step 6: Remove shows-only branches/imports/configuration from `CollectionView.vue`** while preserving the other three collection layouts.
- [ ] **Step 7: Run `npm test`, `npm run build`, and Playwright via CI**; fix only extraction regressions.

### Task 3: Extract the shows form

**Files:**
- Create: `frontend/src/components/ShowForm.vue`
- Modify: `frontend/src/components/RecordForm.vue`
- Modify: `frontend/src/App.vue`
- Test: `frontend/tests/shows.test.ts`
- Test: `frontend/e2e/workspace.spec.ts`

**Interfaces:**
- `ShowForm` props: `{ item?: Show; busy: boolean; error: string }`; emits `close`, `save(data)`, `remove(item)`.
- Consumes `normalizeShowPayload` from Task 1.
- `RecordForm` remains for `tasks | expenses | milestones` only; its save payloads remain unchanged.

- [ ] **Step 1: Add failing helper tests** for metadata application into a draft and poster clear/local-upload normalization where pure state transformation is involved.
- [ ] **Step 2: Run `npm test -- shows.test.ts`** and confirm RED for the missing helper behavior.
- [ ] **Step 3: Add minimal pure helper behavior** to `src/shows.ts`, then confirm the focused tests GREEN.
- [ ] **Step 4: Implement `ShowForm.vue`** by moving the existing show defaults, metadata source/search/apply flow, poster upload/clear state, fields, validation, and modal footer without changing labels or API paths.
- [ ] **Step 5: Simplify `RecordForm.vue`** to tasks/expenses/milestones and remove `api`, `uploadPoster`, metadata, poster, and show-specific normalization imports/state.
- [ ] **Step 6: Wire `App.vue`** to render `ShowForm` when `editing.collection === "shows"`, keeping deletion confirmation in the existing `remove()` path.
- [ ] **Step 7: Expand/retain Playwright coverage** for Bangumi/TMDB selection, metadata fill, local poster upload, clear/edit/delete, and modal error behavior.
- [ ] **Step 8: Run frontend unit/build and full browser CI**.

### Task 4: Cleanup, documentation, and full verification

**Files:**
- Modify: `docs/HANDOFF.md`
- Modify only if required by extraction: `frontend/src/styles.css`

**Interfaces:**
- No new external interface; this task proves the refactor is contract-neutral.

- [ ] **Step 1: Search for stale shows branches** in `CollectionView.vue` and `RecordForm.vue`; remove duplicate implementation, unused imports, and dead CSS only when no longer referenced.
- [ ] **Step 2: Run the complete CI-equivalent checks:** backend pytest/Ruff/deploy tests, frontend Vitest + production build, Docker desktop/mobile Playwright, persistence/redeploy jobs.
- [ ] **Step 3: Update `docs/HANDOFF.md`** with exact commits and verified CI run IDs; do not claim local Docker verification because this execution environment cannot clone/run Docker locally.
- [ ] **Step 4: Review diff against the spec:** confirm no migration/backend contract changes and no unrelated refactor.
- [ ] **Step 5: After branch CI is fully green, follow the repository-authorized delivery flow to merge/fast-forward into `main`; NAS deployment remains user-run."
