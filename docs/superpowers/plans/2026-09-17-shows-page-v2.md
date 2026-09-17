# Shows Page V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add richer show metadata and completion tracking, then improve the show form, cards, and type-grouped page without changing the existing show CRUD route family.

**Architecture:** Extend the existing `Show` row and `ShowPayload` rather than introducing a metadata table. Keep metadata lookup in `metadata.py`, normalize frontend show behavior in `shows.ts`, and let `ShowsView`, `ShowCard`, and `ShowForm` remain focused on grouping, display, and editing respectively.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, SQLite, Vue 3, TypeScript, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-17-shows-page-v2-design.md`

## Global Constraints

- Preserve `/api/shows` CRUD, poster proxy/upload, and per-user ownership semantics.
- New database columns are nullable and old SQLite databases must upgrade automatically.
- First transition to `completed` fills an empty `completed_on`; an existing date is never overwritten automatically.
- Re-scraping metadata must not overwrite progress, status, score, notes, update weekday, or completed date.
- Movie UI must not expose episode progress, season, weekday, progress bar, or `+1` episode controls.
- External source links must be HTTP(S), open in a new tab, and use `rel="noopener noreferrer"`.
- Full CI must pass before merge to `main`; do not deploy NAS.

---

### Task 1: Persist richer show fields and completion semantics

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/database.py`
- Modify: `backend/app/records.py`
- Test: `backend/tests/test_api.py` and/or the existing show API test module

**Interfaces:**
- Produces `Show.release_year: int | None`, `Show.completed_on: date | None`, `Show.source_url: str | None`.
- `ShowPayload` accepts/returns the same fields.
- Show create/update guarantees: if resulting status is `completed` and `completed_on` is null, persist the request-local current date; otherwise preserve supplied/existing date.

- [ ] **Step 1: Write failing API and migration tests**

Add tests that create/read/update all three fields, reject invalid years/URL schemes, migrate an old `shows` table, and verify a first `watching -> completed` update fills `completed_on` while a later completed update does not replace it.

- [ ] **Step 2: Run focused backend tests and verify failure**

Run: `cd backend && pytest -q tests -k 'show or migration'`
Expected: FAIL because the three fields and completion behavior do not exist.

- [ ] **Step 3: Add model/schema/migration fields**

Use nullable `Integer`, `Date`, and `Text` columns. Validate `release_year` as a strict integer in a practical bounded range and `source_url` as an optional max-length string whose parsed scheme is only `http` or `https`.

- [ ] **Step 4: Implement completion transition in the show CRUD path**

Apply the default only after merging a PATCH with the stored row, so PATCH and POST share the invariant. Do not overwrite a non-null date.

- [ ] **Step 5: Run backend tests**

Run: `cd backend && pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: track richer show metadata"
```

### Task 2: Return year and canonical source URL from metadata lookup

**Files:**
- Modify: `backend/app/metadata.py`
- Test: existing metadata tests under `backend/tests/`

**Interfaces:**
- Metadata result adds `release_year: number | null` and `source_url: string | null`.
- Bangumi URL: `https://bgm.tv/subject/{id}`.
- TMDB URL: `https://www.themoviedb.org/tv/{id}` or `https://www.themoviedb.org/movie/{id}`.

- [ ] **Step 1: Add failing provider tests**

Assert Bangumi and TMDB fixtures return year parsed from provider date plus the exact canonical source URL for anime/TV/movie results.

- [ ] **Step 2: Run metadata tests and verify failure**

Run: `cd backend && pytest -q tests -k metadata`
Expected: FAIL on missing keys.

- [ ] **Step 3: Implement provider mapping**

Add a small date-to-year helper that returns null for missing/malformed dates, then populate both new keys without changing outbound request behavior.

- [ ] **Step 4: Run metadata and full backend tests**

Run: `cd backend && pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/metadata.py backend/tests
git commit -m "feat: enrich show scrape results"
```

### Task 3: Extend frontend show domain helpers

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/shows.ts`
- Modify: `frontend/tests/shows.test.ts`

**Interfaces:**
- `Show` and `ShowFormDraft` include `release_year`, `completed_on`, `source_url`.
- `showMetadataPatch()` maps all scraper-owned fields including year/link but excludes user-owned viewing fields.
- Add `groupShowsByType(shows)` returning non-empty groups in fixed order `tv`, `anime`, `movie`.

- [ ] **Step 1: Write failing helper tests**

Test normalization of the new nullable fields, metadata patch inclusion/exclusion, and deterministic grouping/order after filtering.

- [ ] **Step 2: Run Vitest and verify failure**

Run: `cd frontend && npm test -- --run tests/shows.test.ts`
Expected: FAIL because the fields/group helper are absent.

- [ ] **Step 3: Implement types and pure helpers**

Keep grouping and normalization framework-independent so `ShowsView` only renders computed results.

- [ ] **Step 4: Run focused frontend tests**

Run: `cd frontend && npm test -- --run tests/shows.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/shows.ts frontend/tests/shows.test.ts
git commit -m "feat: extend show frontend model"
```

### Task 4: Turn ShowForm into a complete media-aware editor

**Files:**
- Modify: `frontend/src/components/ShowForm.vue`
- Test: `frontend/e2e/shows-refactor.spec.ts`

**Interfaces:**
- Existing `save`, `close`, `remove` events remain unchanged.
- Metadata lookup works for both create and edit.
- Movie mode hides episode/season/weekday controls; TV/anime show them.

- [ ] **Step 1: Extend E2E with failing form assertions**

Cover year, completed date, source URL, edit-time re-scrape controls, and media-type conditional fields. Verify choosing completed with an empty completion date presents today's date before save.

- [ ] **Step 2: Run focused E2E and verify failure**

Run the repository's existing Playwright command targeting `shows-refactor.spec.ts`.
Expected: FAIL on missing fields/controls.

- [ ] **Step 3: Reorganize form into sections and expose fields**

Keep the current modal/event contract. Set `canLookup` true for edit, render source metadata readably, and make the saved payload pass through `normalizeShowPayload`.

- [ ] **Step 4: Protect user-owned fields during metadata application**

Only apply `showMetadataPatch(result)`; do not mutate status/progress/score/notes/update weekday/completed date.

- [ ] **Step 5: Run frontend unit/build and focused E2E**

Run: `cd frontend && npm test -- --run && npm run build`, then the focused Playwright spec.
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ShowForm.vue frontend/e2e/shows-refactor.spec.ts
git commit -m "feat: expand show editor"
```

### Task 5: Redesign cards and type-grouped show page

**Files:**
- Modify: `frontend/src/components/ShowCard.vue`
- Modify: `frontend/src/views/ShowsView.vue`
- Modify: the existing frontend stylesheet(s) containing `.show-card`, `.has-shows`, `.shows-stats`
- Test: `frontend/e2e/shows-refactor.spec.ts`

**Interfaces:**
- `ShowCard` keeps `edit(item)` and `advance(id)` events.
- Source-linked title opens `source_url`; cover remains edit affordance.
- `ShowsView` filters first, then calls `groupShowsByType` and renders only non-empty groups.

- [ ] **Step 1: Add failing desktop/mobile E2E assertions**

Create TV, anime, and movie fixtures. Assert visible group headings/counts, source title link attributes, movie absence of `+1`/episode progress, TV/anime progress controls, and combined search/status filtering across groups.

- [ ] **Step 2: Run focused E2E and verify failure**

Run the existing Playwright command targeting `shows-refactor.spec.ts` in desktop and mobile projects.
Expected: FAIL on grouping/layout semantics.

- [ ] **Step 3: Implement semantic card hierarchy**

Render title/link, status/type/year, media-specific secondary metadata, two-line notes, and progress only for TV/anime. Keep score visually prominent and keep cover click editing.

- [ ] **Step 4: Implement grouped page rendering**

Replace the single `v-for` grid with ordered non-empty sections. Preserve the existing search box, status tabs, stats, empty states, and create action.

- [ ] **Step 5: Add responsive CSS**

Keep desktop cards compact and mobile controls touch-friendly; ensure metadata wraps instead of overflowing and grouped headings remain visually subordinate to the page heading.

- [ ] **Step 6: Run frontend verification**

Run: `cd frontend && npm test -- --run && npm run build`, then focused desktop/mobile E2E.
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ShowCard.vue frontend/src/views/ShowsView.vue frontend/src frontend/e2e/shows-refactor.spec.ts
git commit -m "feat: redesign grouped shows page"
```

### Task 6: Full regression, docs, and integration

**Files:**
- Modify: `docs/HANDOFF.md`
- Modify tests only if a genuine regression in the new behavior is discovered; do not weaken assertions.

**Interfaces:**
- Produces a branch ready for PR/merge under the repository's authorized workflow.

- [ ] **Step 1: Run repository-wide verification**

Run the repo-standard `make test` plus full Docker/Playwright CI-equivalent commands documented by the repository.
Expected: all checks PASS.

- [ ] **Step 2: Update HANDOFF**

Record the three new fields, completion-date rule, scrape link/year behavior, form/card/grouping changes, migration compatibility, and exact verification evidence. State explicitly that NAS was not deployed.

- [ ] **Step 3: Commit documentation**

```bash
git add docs/HANDOFF.md
git commit -m "docs: record shows page v2 verification"
```

- [ ] **Step 4: Push/open PR and verify GitHub CI**

Push `codex/shows-page-v2`, open a PR to `main`, and wait for all applicable GitHub CI checks to complete successfully.

- [ ] **Step 5: Merge only after green CI**

Merge to `main` under the standing repository authorization, then verify the `main` push CI is successful. Do not deploy NAS.
