# Digital Life v1 API contract

Base `/api`, same-origin browser fetch with credentials. JSON, errors `{detail: string}` (validation errors may use FastAPI detail array). All data routes require authentication. All POST/PATCH/DELETE except login require `X-CSRF-Token` matching current session. Login requires same-origin Origin validation when Origin is supplied; all unsafe requests reject conflicting Origin. No public registration/setup endpoints. Administrator initialization via backend CLI.

## Authentication
- `POST /auth/login` `{username,password}` → `{user,csrf_token}` and HttpOnly session cookie.
- `GET /auth/session` → `{user,csrf_token}` or 401.
- `POST /auth/logout` → 204; revoke session and clear cookie.
- `PATCH /auth/profile` `{display_name,birthday,timezone,theme}` → User. Each field optional.
- `POST /auth/password` `{current_password,new_password}` → 204, invalidate all own sessions.
User: `{id:number,username:string,display_name:string,birthday:string|null,timezone:string,theme:'light'|'dark'|'system',is_admin:boolean,is_active:boolean}`.
Username 3–32 chars letters digits underscore hyphen. Password 12–128 chars. Display name 1–60 chars. Dates ISO YYYY-MM-DD. Timezone valid IANA. Theme default light; timezone default Asia/Shanghai.

## Collections
GET `/tasks`, `/expenses`, `/shows`, `/milestones` returns array of owned objects. POST returns created object (201). PATCH `/<collection>/<id>` returns updated object. DELETE same returns 204. Foreign IDs always 404; client cannot choose user_id. Each object includes numeric id. POST and PATCH forbid extra keys. Deleted records disappear permanently after UI confirmation.

Task: `{id,title,notes,status,due_date,priority,created_at}`. title 1–160 chars, notes max 4000 default '', status todo|doing|waiting|done default todo, due_date nullable default null, priority low|normal|high default normal. created_at server ISO datetime. PATCH accepts all except id/created_at.

Expense: `{id,title,amount_cents,currency,period_months,next_due,anchor_day,active,notes}`. title 1–120, amount_cents integer 1–100000000, currency CNY|USD|EUR|JPY|HKD default CNY, period_months 1|3|12 default 1, next_due required date, anchor_day integer 1–31 default next_due day, active default true, notes max 4000 default ''. PATCH accepts all except id. `POST /expenses/<id>/pay` → expense with next_due advanced one period using anchor_day (Jan31→Feb28→Mar31); inactive returns 400. This records progression only, not historical bank transactions. Label UI ‘确认本期已付’.

Show: `{id,title,media_type,status,progress,total,score,notes,update_weekday,source,source_id,source_url,poster_path,seasons,air_status,release_year,completed_on}`. title 1–160, media_type anime|tv|movie default tv, status planned|watching|completed|paused default planned, progress integer 0–1000000 default 0, total nullable integer 1–1000000 default null, progress≤total if known. score nullable integer 1–10. notes max4000 default '', update_weekday null or 0–6 Monday–Sunday. source bangumi|tmdb nullable, source_id nullable integer ≥1, source_url nullable http(s) URL max 500, poster_path nullable max 500, seasons nullable 1–1000, air_status airing|ended|upcoming|released nullable, release_year nullable 1000–9999, completed_on nullable ISO date. `POST /shows/<id>/advance` increments progress, sets watching or completed at total, at total returns unchanged; unknown-total progress at 1000000 returns 400. PATCH accepts all except id.

`completed_on` 由服务端派生：当结果状态为 `completed` 且 `completed_on` 为空时按用户时区填入当天日期；已有日期不会被自动覆盖。POST、PATCH 与 `/advance` 共用该规则（`app/shows/service.py`，字段见 Alembic `0007`）。

Milestone: `{id,title,date,repeats_yearly,notes}` title 1–120, date required, repeats_yearly false default, notes max4000 default ''. PATCH accepts all except id.

`GET /export` returns JSON object with user (no hashes/sessions), tasks, expenses, shows, milestones. Only own data. Client downloads through authenticated fetch.

## Administration
GET `/admin/users` → User[]. POST `{username,password,display_name}` → User (201, ordinary user). PATCH `/admin/users/<id>` `{display_name?,is_active?,password?}` → User. Disallow administrator self-disable; reset/disable revokes target sessions. Ordinary user gets 403. Admin does not bypass collection ownership.

## Server and operator CLI
`GET /health` (outside /api) → `{status:'ok'}` only when database is usable, no private details.
Backend CLI via `python -m app.cli`: `migrate`, `create-admin --username USER` (password via env DIGITAL_LIFE_ADMIN_PASSWORD or hidden prompt), `backup --output PATH`, `restore --input PATH` (offline only; runner responsibility stop backend). Database env `DIGITAL_LIFE_DATA_DIR` default ../data resolved; db filename digital-life.db. Cookie env `DIGITAL_LIFE_SECURE_COOKIE` default false for LAN; true with HTTPS. Session TTL 14 days. `DIGITAL_LIFE_TRUSTED_ORIGINS` optional comma-separated exact origins for reverse proxy HTTPS; derive origin from request scheme/host without blindly trusting forwarded headers. SQLite WAL, foreign keys, busy timeout. App startup runs idempotent migrations, never resets data or seeds a default password. CLI backup uses SQLite backup API; restore validates schema and integrity before replacement, removes stale WAL/SHM only while offline.

## 周期维护（2026-09-15）

完整字段和状态码见 `docs/superpowers/specs/2026-09-15-maintenance-design.md`。

`GET/POST /api/maintenance`、`GET/PATCH/DELETE /api/maintenance/{id}` 提供独立账号的维护事项。创建必填 `title`、`last_completed`、`period_value`、`period_unit`（days/months）；默认 `notes=''`、`remind_days=7`、`active=true`。响应含服务器计算的 `last_completed` 和 `next_due`。PATCH 仅修改事项配置，日期通过历史维护。

`POST /api/maintenance/{id}/complete` 接收 `completed_on`、可选 `cost_cents`、`currency`、`notes`，201 返回更新后的事项。`GET /api/maintenance/{id}/history` 返回按日期、ID倒序的历史；`PATCH /api/maintenance/{id}/history/{log_id}` 修改历史日期、费用、币种或备注，200 返回更新后的事项。同日重复409、未来/越界日期422、停用事项新增完成400、他人资源404。创建时生成首条历史，最新完成日期取全部历史最大值。DELETE 事项级联删除历史。

`GET /api/export` 新增 `maintenance`、`maintenance_logs` 数组，仍仅含当前用户记录。

## 统计与导入（2026-09-16）

`GET /api/stats?end_month=YYYY-MM` 返回以 end_month 结尾的连续 12 个月窗口：每月 `{month, expense_due: {币种: 分}, maintenance_cost: {币种: 分}}`，以及 `shows` 汇总 `{watching,planned,completed,paused,episodes_watched}`。费用口径与「本月应付」一致（仅启用中、从 next_due 整周期外推、不假设支付、月末 anchor、不回溯）；维护费用来自完成历史 `cost_cents` 按完成月归集。非法/缺失月份 422；未登录 401；仅含当前会话用户数据。

`POST /api/import` 接收 `/api/export` 生成的完整 JSON 对象，整体替换当前账号的生活记录（tasks、expenses、shows、milestones、maintenance 及 maintenance_logs），返回 `{imported: {各集合计数}}`。要求文件含 `user` 对象标记；集合列表缺失按空处理（兼容旧版导出）；单集合上限 10,000、总数上限 50,000；逐条按创建校验规则验证，首条无效即 422 且不改动现有数据；维护事项 id 引用、同日重复历史、日期越界均 422。导入后 `last_completed`/`next_due` 从导入的历史重算。不修改登录、密码和个人资料；不影响其他账号。

## 文字随记（2026-09-16）

`GET/POST /api/notes`、`GET/PATCH/DELETE /api/notes/{id}`，与其他集合一致的归属与校验规则。Note：`{id,content,entry_date,created_at}`；content 1–4000 字符必填，entry_date YYYY-MM-DD 必填（允许过去日期补录），created_at 服务器时间。同日多条允许；按 id 倒序返回。导出为 `notes` 数组；导入支持 `notes` 键（旧导出缺省为空）。数据表由 Alembic `0003` 创建；CLI 恢复严格校验 `0003`。

## 追番元数据搜索（2026-09-16，可选联网功能）

`GET /api/shows/metadata?keyword=1..80&media_type=anime|tv|movie&source=bangumi|tmdb`（登录会话）→ `{results:[{source,source_id,source_url,title,original_title,air_date,release_year,total_episodes,platform,image,seasons,air_status}]}`，最多 8 条。`source_url` 为 bangumi `https://bgm.tv/subject/{id}` 或 tmdb `https://www.themoviedb.org/{tv|movie}/{id}`；`release_year` 取首播/上映日期前四位，缺失或非法为 null。实现与路由位于 `app/shows/metadata.py`。数据源由前端显式选择：bangumi（type 2 动画 / type 6 三次元，image 来自 lain.bgm.tv）或 tmdb（需 `DIGITAL_LIFE_TMDB_API_KEY`，逐候选拉取详情获得 seasons 与 air_status：airing/ended/upcoming/released，image 来自 image.tmdb.org）。仅在用户手动触发时调用一次；未知 media_type/source 400、TMDB 未配置 key 400、关键词空白/超长 422、上游任何故障 502、功能禁用 503。

`GET /api/shows/{id}/poster`（登录会话）返回该条目的封面图片：后端仅从 image.tmdb.org / lain.bgm.tv 白名单主机下载（上限 5MB，JPEG/PNG/WebP），按账号归属校验，缓存于数据目录 `posters/`，响应 `Cache-Control: private, max-age=604800`；无封面 404、来源不授信 400、下载失败 502。Show 记录新增可选字段 `source/source_id/poster_path/seasons/air_status`（Alembic `0004`），导出/导入完整支持。不落库、不自动写入；该路由注册在通用 `/api/shows/{id}` 之前。

## 打卡（2026-09-16）

`GET/POST /api/checkins`、`GET/PATCH/DELETE /api/checkins/{id}` 提供独立账号的打卡项目。CheckIn：`{id,title,notes,kind:'daily'|'ongoing',active,created_at}`，title 1–120，notes ≤4000；列表响应额外含 `days`（最近 400 个已打卡日期，升序）与 `total_count`。`POST /api/checkins/{id}/check` 接收 `{checked_on?,note?}`，缺省为用户时区今天；未来日期 422、同日重复 409、已归档 400，201 返回更新后项目。`DELETE /api/checkins/{id}/check/{checked_on}` 撤销某天（无记录 404）。`GET /api/checkins/{id}/logs` 按日期倒序。删除项目级联删除记录。导出为 `checkins`、`checkin_logs`；导入按 id 映射重建，悬空引用/同日重复 422。数据表由 Alembic `0005` 创建；CLI 恢复严格校验 `0005`。

## 在做（2026-09-16）

`GET/POST /api/projects`、`GET/PATCH/DELETE /api/projects/{id}`，通用集合规则。Project：`{id,title,notes,status:'active'|'paused'|'done',created_at}`，title 1–120，notes ≤4000，status 默认 active。导出为 `projects`；导入支持，且旧导出中 `checkins.kind=='ongoing'` 的行会转换为 projects（其打卡记录以文字摘要并入 notes）。同期打卡的 kind 仅接受 `daily`（创建/修改 ongoing 返回 422）。Alembic `0006` 建表并把已有 ongoing 打卡迁入 projects；CLI 恢复严格校验 `0006`。
