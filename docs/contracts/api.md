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

Expense: `{id,title,amount_cents,currency,period_months,next_due,anchor_day,active,notes,account_id,category_id,payee_id}`. title 1–120, amount_cents integer 1–100000000, currency CNY|USD|EUR|JPY|HKD default CNY, period_months 1|3|12 default 1, next_due required date, anchor_day integer 1–31 default next_due day, active default true, notes max 4000 default ''. `account_id/category_id/payee_id` 可空，指向记账域的账户/分类/商户（Alembic `0008`）；给出时必须属于当前用户，否则 422；账单的分类必须是支出类型。PATCH accepts all except id.

`POST /expenses/<id>/pay` 接收可选 `{account_id?,category_id?,payee_id?,book_id?}`，返回账单对象外加 `entry_id`。请求体缺省时沿用账单自身的绑定；只要最终生效账户非空，就在同一事务内生成一条 `kind='expense'` 的记账流水并把 `entry_id` 指回该流水，否则与旧行为一致、仅推进日期。`book_id` 的生效顺序同为请求体优先、否则沿用账单自身标签。非交易类字段（账户、分类、商户、账本）在推进 `next_due` **之前** 校验，校验失败不改变 `next_due`。next_due advanced one period using anchor_day (Jan31→Feb28→Mar31); inactive returns 400. Label UI ‘确认本期已付’。

Show: `{id,title,media_type,status,progress,total,score,notes,update_weekday,source,source_id,source_url,poster_path,seasons,air_status,release_year,completed_on}`. title 1–160, media_type anime|tv|movie default tv, status planned|watching|completed|paused default planned, progress integer 0–1000000 default 0, total nullable integer 1–1000000 default null, progress≤total if known. score nullable integer 1–10. notes max4000 default '', update_weekday null or 0–6 Monday–Sunday. source bangumi|tmdb nullable, source_id nullable integer ≥1, source_url nullable http(s) URL max 500, poster_path nullable max 500, seasons nullable 1–1000, air_status airing|ended|upcoming|released nullable, release_year nullable 1000–9999, completed_on nullable ISO date. `POST /shows/<id>/advance` increments progress, sets watching or completed at total, at total returns unchanged; unknown-total progress at 1000000 returns 400. PATCH accepts all except id.

`completed_on` 由服务端派生：当结果状态为 `completed` 且 `completed_on` 为空时按用户时区填入当天日期；已有日期不会被自动覆盖。POST、PATCH 与 `/advance` 共用该规则（`app/shows/service.py`，字段见 Alembic `0007`）。

Milestone: `{id,title,date,repeats_yearly,notes}` title 1–120, date required, repeats_yearly false default, notes max4000 default ''. PATCH accepts all except id.

`GET /export` returns JSON object with user (no hashes/sessions), tasks, expenses, shows, milestones, notes, checkins, projects, bookmarks, maintenance, maintenance_logs, plus 记账域的 `ledger_books`、`ledger_accounts`、`ledger_categories`、`ledger_payees`、`ledger_entries`。账户余额与账本金额都是派生值，**不导出**。Only own data. Client downloads through authenticated fetch。

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

`GET /api/stats?end_month=YYYY-MM&book_id=<id>` 返回以 end_month 结尾的连续 12 个月窗口：每月 `{month, expense_due: {币种: 分}, maintenance_cost: {币种: 分}, ledger_income: {币种: 分}, ledger_expense: {币种: 分}}`，以及 `shows` 汇总 `{watching,planned,completed,paused,episodes_watched}`。费用口径与「本月应付」一致（仅启用中、从 next_due 整周期外推、不假设支付、月末 anchor、不回溯）；维护费用来自完成历史 `cost_cents` 按完成月归集。**投影与实付并列**：`expense_due` 是账单按周期外推的应付，`ledger_expense`/`ledger_income` 是记账流水按 `occurred_on` 归集的真实收支（转账不计入）。可选 `book_id` 把账单与流水两路口径同时收窄到该账本（`maintenance_cost` 与 `shows` 不受影响，维护与追剧不属账本维度）。另含 `ledger.categories`（仅 end_month、支出与收入分类合计，未分类不计）与 `ledger.payees`（仅支出、降序取前 8，无商户归为 `未标注商户`）。非法/缺失月份 422；未登录 401；仅含当前会话用户数据。

`POST /api/import` 接收 `/api/export` 生成的完整 JSON 对象，整体替换当前账号的生活记录（tasks、expenses、shows、milestones、maintenance 及 maintenance_logs，以及 ledger_books、ledger_accounts、ledger_categories、ledger_payees、ledger_entries），返回 `{imported: {各集合计数}}`。要求文件含 `user` 对象标记；集合列表缺失按空处理（兼容旧版导出）；单集合上限 10,000、总数上限 50,000；逐条按创建校验规则验证，首条无效即 422 且不改动现有数据；维护事项 id 引用、同日重复历史、日期越界均 422。记账域先清空旧行再重建，账本/账户/分类/商户/账单的 id 全量重映射，流水的账户与分类引用必须能在同文件内解析（悬空 422），`book_id` 为 null 或缺失时落到该账号的默认账本；旧版导出（无 `ledger_books`）若含账单或流水，在同一事务内补建一条默认账本承接，**校验失败回滚时不留下任何改动**。商户按 `name_key`（`strip().casefold()`）归并，同名先合并再复用。导入后 `last_completed`/`next_due` 从导入的历史重算。不修改登录、密码和个人资料；不影响其他账号。

## 文字随记（2026-09-16）

`GET/POST /api/notes`、`GET/PATCH/DELETE /api/notes/{id}`，与其他集合一致的归属与校验规则。Note：`{id,content,entry_date,created_at}`；content 1–4000 字符必填，entry_date YYYY-MM-DD 必填（允许过去日期补录），created_at 服务器时间。同日多条允许；按 id 倒序返回。导出为 `notes` 数组；导入支持 `notes` 键（旧导出缺省为空）。数据表由 Alembic `0003` 创建；CLI 恢复严格校验 `0003`。

## 追番元数据搜索（2026-09-16，可选联网功能）

`GET /api/shows/metadata?keyword=1..80&media_type=anime|tv|movie&source=bangumi|tmdb`（登录会话）→ `{results:[{source,source_id,source_url,title,original_title,air_date,release_year,total_episodes,platform,image,seasons,air_status}]}`，最多 8 条。`source_url` 为 bangumi `https://bgm.tv/subject/{id}` 或 tmdb `https://www.themoviedb.org/{tv|movie}/{id}`；`release_year` 取首播/上映日期前四位，缺失或非法为 null。实现与路由位于 `app/shows/metadata.py`。数据源由前端显式选择：bangumi（type 2 动画 / type 6 三次元，image 来自 lain.bgm.tv）或 tmdb（需 `DIGITAL_LIFE_TMDB_API_KEY`，逐候选拉取详情获得 seasons 与 air_status：airing/ended/upcoming/released，image 来自 image.tmdb.org）。仅在用户手动触发时调用一次；未知 media_type/source 400、TMDB 未配置 key 400、关键词空白/超长 422、上游任何故障 502、功能禁用 503。

`GET /api/shows/{id}/poster`（登录会话）返回该条目的封面图片：后端仅从 image.tmdb.org / lain.bgm.tv 白名单主机下载（上限 5MB，JPEG/PNG/WebP），按账号归属校验，缓存于数据目录 `posters/`，响应 `Cache-Control: private, max-age=604800`；无封面 404、来源不授信 400、下载失败 502。Show 记录新增可选字段 `source/source_id/poster_path/seasons/air_status`（Alembic `0004`），导出/导入完整支持。不落库、不自动写入；该路由注册在通用 `/api/shows/{id}` 之前。

## 打卡（2026-09-16）

`GET/POST /api/checkins`、`GET/PATCH/DELETE /api/checkins/{id}` 提供独立账号的打卡项目。CheckIn：`{id,title,notes,kind:'daily'|'ongoing',active,created_at}`，title 1–120，notes ≤4000；列表响应额外含 `days`（最近 400 个已打卡日期，升序）与 `total_count`。`POST /api/checkins/{id}/check` 接收 `{checked_on?,note?}`，缺省为用户时区今天；未来日期 422、同日重复 409、已归档 400，201 返回更新后项目。`DELETE /api/checkins/{id}/check/{checked_on}` 撤销某天（无记录 404）。`GET /api/checkins/{id}/logs` 按日期倒序。删除项目级联删除记录。导出为 `checkins`、`checkin_logs`；导入按 id 映射重建，悬空引用/同日重复 422。数据表由 Alembic `0005` 创建；CLI 恢复严格校验 `0005`。

## 在做（2026-09-16）

`GET/POST /api/projects`、`GET/PATCH/DELETE /api/projects/{id}`，通用集合规则。Project：`{id,title,notes,status:'active'|'paused'|'done',created_at}`，title 1–120，notes ≤4000，status 默认 active。导出为 `projects`；导入支持，且旧导出中 `checkins.kind=='ongoing'` 的行会转换为 projects（其打卡记录以文字摘要并入 notes）。同期打卡的 kind 仅接受 `daily`（创建/修改 ongoing 返回 422）。Alembic `0006` 建表并把已有 ongoing 打卡迁入 projects；CLI 恢复严格校验 `0006`。

## 记账（2026-09-25，账本 2026-09-26）

完整设计见 `docs/superpowers/specs/2026-09-25-ledger-design.md`。五个集合的路由前缀为 `/api/ledger`，归属、CSRF、Origin 规则与其他集合一致。

**账本 `GET/POST /api/ledger/books`、`GET/PATCH/DELETE /api/ledger/books/{id}`**（2026-09-26）
Book：`{id,name,archived,sort_order,created_at}`。name 1–20（前后空白自动去除），同一账号内唯一（重复 409 「已存在同名账本」）；archived 默认 false；sort_order 0–1000。账本是**贴在流水与账单上的标签**，不是第二套账户：账户、分类、商户仍然全局共享，余额也仍在账户维度派生，跨账本合计不会被切开。被流水或账单引用的账本删除返回 409（「该账本已有流水或账单，请改为归档」），归档即可从选择器中退出。列表按 `sort_order`、id 升序。

每个账号在首次需要时自动拥有一个默认账本（`ensure_default_book`，名字 `日常`，取自 `sort_order` 最小者）：迁移 `0010` 为历史数据补建，导入旧版导出时在同一事务内补建，手工记账未指定 `book_id` 时落到它。前端对真正为 null 的行显示为 `未归类`（迁移与导入正常路径不会产生这种行，仅作为兜底展示）。

**账户 `GET/POST /api/ledger/accounts`、`GET/PATCH/DELETE /api/ledger/accounts/{id}`**
Account：`{id,name,kind,currency,opening_balance_cents,archived,sort_order,created_at,balance_cents}`。name 1–40（前后空白自动去除）；kind `cash|debit|credit|ewallet|invest|other` 默认 `debit`；opening_balance_cents 整数 −1,000,000,000..1,000,000,000 默认 0；sort_order 0–1000。**`balance_cents` 是派生值**（期初 + 收入 − 支出 ± 转账），不在任何写入接口中接受，导出时也不落盘；转账对余额两侧同时生效。删除被流水或账单引用的账户返回 409。

**分类 `GET/POST /api/ledger/categories`、`GET/PATCH/DELETE /api/ledger/categories/{id}`**
Category：`{id,name,kind,archived,sort_order,created_at}`。name 1–20，kind `income|expense` 必填，同一账号内 `(kind, name)` 唯一。**PATCH 不接受 `kind`**：改动它会重写历史口径。首次访问列表时若该账号一条分类都没有，自动播种支出（餐饮/交通/居住/购物/医疗/学习/娱乐/人情/其他）与收入（工资/奖金/理财/兼职/报销/其他）默认集，播种幂等 —— 只要已有任意一条分类就不覆盖，自定义分类集得以保留。删除被引用分类返回 409。

**商户 `GET/POST /api/ledger/payees`、`GET/PATCH/DELETE /api/ledger/payees/{id}`**
Payee：`{id,name,kind,archived,sort_order,created_at}`。name 1–40，kind `merchant|org|person` 默认 `merchant`。落库时以 `name_key = name.strip().casefold()` 去重（同账号唯一），避免大小写/空白造成的近似重复。删除被引用商户返回 409。

`POST /api/ledger/payees/{id}/merge` `{into: 商户id}` 把源商户的全部引用改指目标商户（流水与账单各返回条数）并在同一事务内删除源商户，响应 `{entries, expenses}`；`into` 指向自身 422，目标不存在或非本人 404。

**流水 `GET/POST /api/ledger/entries`、`GET/PATCH/DELETE /api/ledger/entries/{id}`**
Entry：`{id,occurred_on,kind,amount_cents,currency,book_id,account_id,from_account_id,to_account_id,category_id,payee_id,note,expense_id,created_at}`。occurred_on 必填且**不得晚于用户时区的今天**（422）；amount_cents 1–100,000,000；currency 默认 CNY，**必须与生效账户币种一致**（422）。`book_id` 可空，指向本人账本，非本人或不存在的账本 422（「账本不存在」）。

三种 kind 的字段组合由模型校验强制：`income`/`expense` 必须给 `account_id`、不得带 from/to；`transfer` 必须同时给 `from_account_id` 与 `to_account_id`，两者不得相同，且不得带 account/category/payee。transfer 的转出与转入账户币种必须一致。分类的 kind 必须与流水 kind 相同；账户、分类、商户都必须属于当前用户，否则 422。`expense_id` 只读，指向自动生成该流水的账单（手工录入为 null）；账单删除时置 null 而不是连带删除流水。

列表支持 `from`/`to`（默认截至用户时区今天）、`kind`、`account_id`、`category_id`、`payee_id`、`book_id` 过滤，并按 `occurred_on`、`id` 倒序。为避免一次请求倾倒整本旧账，默认只返回最近 12 个月窗口且 `limit` 默认 500、上限 2000。`account_id` 过滤把转账的两侧都算作该账户的活动，但转账永远不计入收支；`book_id` 只按标签收窄列表，不影响任何余额。

流水按 `occurred_on` 归入月度统计，转账被排除在收入与支出之外；账户余额与报表都由流水派生，没有需要手工对账的存储余额。

## 书签（2026-09-26）

`GET/POST /api/bookmarks`、`GET/PATCH/DELETE /api/bookmarks/{id}`，归属、CSRF、Origin 规则与其他集合一致；路由前缀 `/api/bookmarks`。Bookmark：`{id,url,title,note,folder,starred,visit_count,last_visited_at,created_at}`。url 只接受 `http`/`https`、长度 ≤2048、不含空白字符，域名需匹配 `[A-Za-z0-9._~%:-]`（拒绝 `javascript:`、`data:` 等伪协议，避免存下来的链接在前端渲染成 XSS，其他非法值 422）；title 1–160；note ≤4000；`folder` 1–60 可空（空串按 null 存，是唯一的分组维度，没有标签关联表）；`starred` 默认 false。列表按 `starred` 降序、id 降序（置顶在前）。

`GET /api/bookmarks?q=&folder=` 支持关键词（标题/网址/备注，`LIKE` 包含匹配）与分组过滤：`folder` 缺省表示全部分组，`folder=` 空串表示仅未分组的条目。

`POST /api/bookmarks/{id}/visit` 把 `visit_count` 加一并写入 `last_visited_at`，只更新这两个计数，不改动可编辑字段；计数失败不影响用户打开链接。

`POST /api/bookmarks/title` `{url}` → `{title}`，**仅用户点击「获取标题」时调用**。后端读取目标页 `<title>`（去标签、`html.unescape`、折叠空白、截断到 160），8 秒超时、最多读 2MB、只接受 `text/*`、手动跟随最多 3 跳且每跳重新校验主机；主机为内网/回环/链路本地/保留地址时 422（域名会先解析再判定，防止指向私网的公网域名），非网页、HTTP ≥400、无标题、重定向过多同样 422；`DIGITAL_LIFE_DISABLE_METADATA=true` 时 503。站点图标不经过后端：由浏览器直接请求 `{origin}/favicon.ico`，失败时前端降级为首字母色块。

导出为 `bookmarks` 数组（含 `visit_count` 与 `last_visited_at`）；导入支持 `bookmarks` 键，旧导出缺省按空处理（导入是整体替换，缺键即清空）。数据表由 Alembic `0009` 创建；CLI 恢复严格校验 `0009`。
