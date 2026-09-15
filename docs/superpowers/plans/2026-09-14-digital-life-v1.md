# Digital Life v1 Implementation Plan

> **For agentic workers:** Execute the tasks below with test-first verification and independent review. Each worker owns its specified directories; shared interfaces are fixed in docs/contracts/api.md.

**Goal:** Deliver a working multiuser life dashboard with NAS Docker deployment and GitHub CI.
**Architecture:** Vue SPA served by Nginx proxies a FastAPI API. SQLite stores user-scoped business records and revocable sessions; Docker Compose persists data on the NAS.
**Tech Stack:** Vue 3, TypeScript, Vite, FastAPI, SQLAlchemy, Alembic, SQLite, uv, pytest, Vitest, Playwright.
**Spec:** docs/superpowers/specs/2026-09-14-digital-life-design.md

## Global constraints
- Personal data isolated by authenticated user, including admin business access and exports.
- Local development → GitHub CI → x86 NAS `git pull --ff-only && ./deploy`.
- Chinese mobile-first UI; no external content API required.
- Lock dependencies; exclude credentials, databases, runtime artifacts from Git.
- Approved implementation starts now; current checkout is an empty dedicated repository on codex/digital-life-v1.
- API interfaces: docs/contracts/api.md. Changes require coordination before altering consumers.

### Task 1: Backend authentication, collections, persistence and operator tools
Files: backend/pyproject.toml, uv.lock, app/{main,config,database,models,schemas,security,auth,records,admin,cli}.py, migrations/, tests/.
- [x] Write failing API integration tests using temporary real SQLite databases and TestClient. Check unauthenticated requests, wrong passwords, CSRF rejection, independent accounts, foreign ID CRUD, admin boundaries and revoked sessions.
```python
assert bob.get(f'/api/tasks/{alice_task_id}').status_code == 404
assert bob.patch(f'/api/tasks/{alice_task_id}', json={'title': 'changed'}, headers=bob_csrf).status_code == 404
```
- [x] Run pytest and observe missing application behavior before implementing routes.
- [x] Implement the shared contract with owner-filtered SQL queries, validated payloads and opaque hashed session tokens. Avoid generic unvalidated JSON storage.
- [x] Write and run boundary tests: Jan31→Feb28→Mar31, progress at total, invalid dates, data after app restart, migration repeated safely, SQLite backup/restore, profile and export isolation.
```python
assert paid['next_due'] == '2027-02-28'
assert paid_again['next_due'] == '2027-03-31'
```
- [x] Lock backend dependencies, run `uv run pytest` and `uv run ruff check .`.

### Task 2: Frontend life workspace
Files: frontend/package.json, package-lock.json, vite.config.ts, src/{App.vue,api.ts,types.ts,styles.css,domain.ts}, src/components/, src/views/, tests/, public/.
- [x] Write failing pure behavior tests for local-calendar days alive, annual leap-day countdown, monthly expense normalization and occurrences within a calendar month; exclude inactive expenses and group currency separately.
```typescript
expect(monthlyCost({amount_cents:12000,period_months:12})).toBe(1000)
```
- [x] Implement shared-contract API client, session bootstrap, sign-in, CSRF mutations and cache clearing on logout/account changes.
- [x] Build real editable task, expense, show and milestone pages, warm green/cream dashboard, single-column mobile layout, bottom navigation, dialogs, loading/error/empty states, profile and admin account forms.
- [x] Implement manual payments, one-episode advance and own-data export. Destructive deletes require confirmation.
- [x] Add PWA manifest, local icons, shell-only service worker. Never cache API/private responses. Theme and timezone reflect current account.
- [x] Verify `npm test`, `npm run build`, then real backend browser flows at desktop/mobile sizes.

### Task 3: Deployment and CI
Files: deploy, scripts/, docker-compose.yml, backend/Dockerfile, frontend/Dockerfile, frontend/nginx.conf, .env.example, .gitignore, .dockerignore, .github/workflows/ci.yml, README.md, Makefile.
- [x] Test deployment with controlled fake Docker process outputs to prove failure exit states, check-only no mutation, first/full/unchanged plans and health-gated success state.
- [x] Implement lock, config creation, build-before-stop, selective rebuild, backup while writes paused, migrate, update, health gate. No global Docker cleanup. Persist data and backup paths; expose frontend only.
- [x] Provide admin initialization, backups and offline restore commands with Chinese documentation.
- [x] CI: frozen installs, backend tests/lint, frontend tests/typecheck/build, amd64 Compose smoke plus real mobile/desktop browser test, persistence after container recreation. Run on every push and PR.
- [x] Validate shell syntax, compose config if Docker available and test deploy runner behavior.

### Task 4: Integration and release
Files: tests/e2e/, playwright.config or frontend e2e config, README.md, docs/.
- [x] Start actual API and frontend locally with a temporary demo data directory and operator-created account.
- [x] Exercise login, create/edit/complete/delete records, export, account switching; capture desktop/mobile screenshots and inspect layout.
- [x] Request independent code review of account isolation, deployment and integrated behavior; fix material issues with regression tests.
- [x] Run all checks once after final fixes, commit and push initial project to user-provided empty repository; ensure main is deployable after CI verification.
- [x] Inspect GitHub Actions results; fix failures and re-run relevant checks. Report actual verification and any external blockers.

## Execution record
- Remote repository is empty. No existing application baseline tests.
- Local Docker CLI is absent; build/start checks will run in GitHub Actions. Local API/browser checks and deployment-script behavior tests remain available.

- 2026-09-15: Implementation committed as `5d41173` and pushed to `main`. Local checks: backend 55, frontend 12, deployment 9, desktop/mobile E2E 8 passed. All three CI jobs passed: https://github.com/zhigu34/digital-life/actions/runs/34920606997. NAS deployment remains an operator step; no NAS host was supplied.
