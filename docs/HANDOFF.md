# Digital Life 接手状态

## 2026-09-26 长期任务卡片可折叠：默认摘要、按需详情、记住偏好

用户要求「长期运行的任务在界面可折叠：默认只展示基本信息与状态摘要，展开后看完整详情（任务进度、执行日志、耗时统计）；折叠状态下仍能感知实时进展；记住折叠/展开偏好；支持批量折叠或展开所有长期任务」。分支 `codex/tasks-collapse`，无数据库迁移（仍停在 `0011`）。

**「耗时统计」按纯派生实现，不新增字段**：已坚持天数（从最早一次打卡算起，没有记录时从最早的开始日期算起；归档分组冻结在归档日）、最近打卡（今天/昨天/N 天前）、累计打卡次数、周期达标 `x/y`。如果用户想要的是"每次打卡花了多少分钟"，那是一个新字段（`task_completions.duration_minutes`）+ 表单输入 + 导出导入，属于下一步，本轮没做。

后端：

- 新增 `GET /api/groups/{gid}/log?limit=1..50`（默认 20）：整个分组的最近完成记录，倒序，每行带 `item_title`。**按需拉取**——只在卡片展开时请求，`GET /api/groups` 仍然不带日志，否则列表响应会随打卡次数增长。`app/groups/service.py` 的 `group_log()` 用一条 join 查询，归属沿用 `owned_group`。

前端（`features/tasks/`）：

- 新增 `collapse.ts`：折叠偏好按**账号**存 `localStorage`（`digital-life:collapsed-groups:<userId>`，默认折叠）。页面按 `user.id` 重建，但浏览器存储会跨账号，所以必须分键；读写失败（隐私模式、配额、损坏 JSON）一律静默降级成默认值，纯函数 + 4 个用例。
- `GroupCard` 分两态：折叠态 = 折叠钮 + 标题 + 构成摘要 + 本期进度徽标 + **每项一行实时状态**（含打卡钮、连续/累计/状态文案）+「还差 N 项：…」+「最近打卡」。展开态再加周期格子、耗时统计块、每项达标率与执行日志（最近 12 条，展开时拉取、变更后作废重取）。
- 变更后在折叠卡片上闪一个「刚刚更新」标记（`afterChange()` 统一挂钩：打卡、撤销、补记、改项、归档、编辑分组都走它）。打卡仍可在折叠态直接完成，日常流程不需要先展开。
- 工具条新增「全部折叠 / 全部展开」，作用于当前筛选下的分组。
- 新建分组后自动展开它并拉日志——刚写完的分组是用户想看的。

**E2E 抓到一个单测与类型检查都抓不到的真 bug**：批量按钮的禁用条件写反，第一次把 `!allCollapsed` 用在「全部折叠」上（已展开时反而禁用），补上 `allExpanded`（混合态两个按钮都可用）后才正确。这类"状态机少了一个态"的错误只有点得动/点不动才能发现。

验证：后端 `pytest` 206 项（新增分组日志用例：跨项倒序、`item_title`、`limit` 边界 422、他人 404）、`ruff check` 与 `ruff format --check` 通过；前端 Vitest 76 项（新增 `collapse.test.ts` 4 项、`periods` 分组统计 5 项）、`vue-tsc`、生产构建通过；**本地 Playwright 52 项（桌面 + 手机）全绿**，其中新增折叠用例覆盖：默认展开刚建的分组 → 批量折叠 → 折叠态打卡后摘要与「刚刚更新」即时变化 → 展开一个（另一个保持折叠）→ 刷新后偏好保留 → 批量展开 → 账号隔离。

**本机仍没有 Docker**，容器与 `docker-e2e` 只能在 GitHub Actions 验证；本轮同样**未执行 NAS 部署**。本次没有迁移，部署只需 `git pull --ff-only && ./deploy`（前端有改动，会重建前端镜像）。

## 2026-09-26 待办与打卡合并为「任务」，长期任务按周期打卡

用户要求「把打卡功能和待办清单合并，支持一次性待办与可设重复周期的长期待办，长期待办自动进入打卡模式，能看清哪些日期完成、哪些没完成」。先出设计稿与可点效果图，用户确认 5 项决策后开工，分支 `codex/tasks-checkin-merge`：

1. **每周/每月 = 本周/本月内完成即可**，不设固定日期。原设计里的"星期几/几号 + 月末锚定"整体删除，周期只由 `repeat_unit` + `start_date` 描述，服务端只存完成日期。
2. **移除打卡页**，数据迁移进长期任务；合并时**不引入多余元素**（不新增页面/导航项/今日概览面板）。
3. **移动端底部第 4 格换成「记账」**（`mobilePrimary`），打卡不再是主入口。
4. **一次性待办是独立选项、不可互转**：所以长期任务没有塞进 `tasks` 表，而是三张新表；待办请求体混入周期字段直接 422。
5. 另外 4 项细节（归档后历史保留到归档日、不做单项停用、达标率窗口 30/8/6、分组名必填）按建议执行。

后端：

- 迁移 `0011` 新建 `task_groups` / `task_group_items` / `task_completions`（`UNIQUE(item_id, completed_on)`），并给 `tasks` 加可空 `completed_on`；**同一迁移把 `checkins`/`checkin_logs` 的数据搬进新表后删掉旧表**：每个旧打卡项变成一个"单项目组 + `repeat_unit='day'` 的打卡项"，`start_date` 取**最早完成日**而不是创建时间 —— 否则历史会凭空长出"漏做"格子。`downgrade` 尽力回写（多分组的项会拆成多个 checkins），生产回退仍走预迁移备份。
- 新域包 `app/groups/`：分组/打卡项 CRUD、`complete`/撤销、`completions?start=&end=`（跨度 ≤366 天）。归属由会话决定，**项只能通过自己的分组解析**（跨组配对 404）。列表接口用固定 4 条查询（分组 → 项 → 完成窗口 → 计数），有专门的查询计数回归用例。
- `records.py` 新增 `sync_task_completion`：`completed_on` 只在 `status` 变成 `done` 的那一刻写入，改回其他状态清空；它不在 `TaskPayload` 里，客户端提交即 422。
- 导出改成 `task_groups`/`task_group_items`/`task_completions` 三键；`imports.py` 仍接受旧导出的 `checkins` + `checkin_logs`（旧的 `kind='ongoing'` 继续转成在做项目），校验失败整体回滚。CLI `SCHEMA_REVISION` 升到 `0011`。
- 顺手把 `uv.lock` 与 `pyproject.toml` 的 `requires-dist` 同步（此前 `python-multipart` 只进了包列表，没进 requires-dist；新版 uv 重跑锁文件带来的顺序漂移一并带入）。

前端：

- 新域包 `features/tasks/`：`TasksView`（一页两段：一次性待办 + 长期任务分组）、`TaskCard`、`GroupCard`、`GroupForm`、`ItemForm`、`HistoryDialog`、`periods.ts`（纯派生）、`useGroups.ts`（自持数据 + 回传快照）、`tasks.css`。`views/CollectionView.vue` 拆成 `views/MilestonesView.vue`（只留重要日子）。
- 周期三态由 `periods.ts` 派生：`done` / `missed`（周期已结束且 0 次）/ `pending`（当前周期，**永远不算漏做**）/ `before`（早于 `start_date` 或晚于 `archived_on`）。周一为周起点、ISO 周号跨年（2027-01-01 属 2026-W53）。
- 今日概览把原来的「接下来，做这些」与「今天还没打卡」两块面板**合并成一块「今天的任务」**：今天到期/逾期的一次性待办 + 当前周期未达标的打卡项（按 每天 → 本周 → 本月 排序）。点长期任务那一行会跳到任务页并直接打卡（`check-request` 请求属性），不复制一份状态。
- 打卡页 `views/CheckInsView.vue`、`src/checkin.ts`、`Records.checkins`、导航项与 `styles.css` 里只服务于旧打卡页的样式（`.checkin-list/.checkin-card/.checkin-stats/.checkin-week/.tag.daily/.tag.ongoing`）一并删除；`.checkin-hit/.checkin-body/.checkin-title-row/.checkin-log-*` 保留，长期任务卡片继续用。

本轮 E2E 抓到两个单测与类型检查都抓不到的**真 bug**：

1. **`RecordForm` 把服务端字段回传导致编辑待办必然 422**：表单用 `{...props.item}` 初始化，`tasks` 新增 `completed_on` 后，编辑任何待办都会把它带回 PATCH，`extra="forbid"` 直接 422（表现是编辑弹窗点保存没反应）。改为只挑表单自己的字段回传。
2. **补记到开始日期之前的完成记录被算成"不在计划内"**：`periodState` 先判 `start_date` 再判完成，导致"今天建的项补昨天的卡"既不高亮也不计入连续。改为**完成记录优先**：录过的日期就是事实，`start_date`/`archived_on` 只管空周期算不算漏做。

验证：后端 `pytest` 205 项通过（新增分组 CRUD/二级归属 404/409/422、导出导入往返与旧 `checkins` 导出兼容、被拒导入不改动现有数据、`0005 → 0011` 数据保全与 `0011 → 0010` 回退、一次性待办 `completed_on`、查询计数不随分组数增长），`ruff check` 与 `ruff format --check` 通过。前端 Vitest 65 项（`periods.test.ts` 17 项覆盖 ISO 跨年周、闰月、三态、连续、达标率分母）、`vue-tsc`、生产构建通过；**本地 Playwright 50 项（桌面 + 手机）全绿**，其中把原打卡用例改写成长期任务用例（建分组 → 今日总览一键打卡 → 撤销/重打 → 周期明细补记昨天 → 每周项"本周已完成 1 次" → 刷新持久化 → 账号隔离）。

分支 CI [Actions #36242689911](https://github.com/zhigu34/digital-life/actions/runs/36242689911)（head `bdf385a`）与 main CI [36243228546](https://github.com/zhigu34/digital-life/actions/runs/36243228546) 的 backend / frontend / docker-e2e 三个 job 全部 success，按既有授权走快进合并。

**本机没有 Docker**：容器构建与 `docker-e2e` 只能在 GitHub Actions 验证，本地结论不含 Docker/NAS 已验证。本轮同样**未执行 NAS 部署**，仍由用户运行 `git pull --ff-only && ./deploy`。这次带 Alembic `0011`，`deploy` 会在迁移前自动备份旧库；迁移会**删除 `checkins`/`checkin_logs` 两张表**并把数据搬进新表，建议部署后在真实数据上确认三件事：原来的打卡项都变成"单项目组 + 每天"且连续天数与累计次数和升级前一致、历史格子没有凭空多出漏做、一次性待办的完成日期为空（升级前没有这个信息）。

## 2026-09-26 记账支持多账本（`fb4e3d2`）

用户要求「记账添加多账本功能，这样可以为专项账目进行记录」。先用一张可点的界面样稿和一张 A/B 对比图把做法说清（题目是「账本该挂在哪里」），用户确认三个取舍后开工，分支 `codex/ledger-books`：

1. **层级 = 挂在流水与账单上**，不是挂在账户上：`ledger_entries` 与 `expenses` 各加可空 `book_id`，账户/分类/商户仍全局共享。这样余额仍是账户维度的一个派生数，切账本永远不改变任何余额；反过来若按账户分账本，同一张卡的钱会被切成两半，与「余额一律由流水派生」这条既有铁律冲突。
2. **本轮不做预算额度**，只归类统计（额度与超支提醒留到下一批）。
3. **字典全局共享**，分类与商户不按账本隔离。

后端：
- 迁移 `0010` 新建 `ledger_books`（`user_id + name` 唯一）并给两列加可空 `book_id`；**SQLite 不能 `ADD COLUMN` 带外键**，故两列不写 REFERENCES，归属由端点守（沿用 `0008` 的先例，删除被引用的账本返回 409 而不级联）。迁移为每个已有账号补建默认账本「日常」并把历史账单与流水归入 —— 否则升级后旧数据会读成「未归类」，看起来像丢了数据。
- `app/ledger` 增 `BookPayload` / `BookView` / `BookPatch`、账本 CRUD、`owned_book` / `book_in_use` 与 `ensure_default_book`（取 `sort_order` 最小者，没有则播种「日常」；`IntegrityError` 时回选，处理并发）。重名 409、被引用时删除 409（提示改用归档）、`book_id` 非本人 422。
- `/api/stats` 增可选 `book_id`，把 `expense_due` 与 `ledger_income`/`ledger_expense` 两路口径同时收窄；`maintenance_cost` 与 `shows` 不受影响（维护与追剧不属账本维度）。`/expenses/{id}/pay` 生成的流水沿用账单自身的账本标签（请求体可覆盖），仍在推进 `next_due` **之前**校验。
- 导出/导入补 `ledger_books`（id 全量重映射）。**导入里踩到一个真 bug**：旧版导出没有账本键，于是调 `ensure_default_book()` 补建 —— 而它会 `commit()`，DELETE 已执行、事务被提前提交，结果是**一次被拒的导入把调用方的记账数据清空了**（由 `test_import_rejects_dangling_ledger_references` 失败暴露）。改为在同一事务内 `LedgerBook(...)` + `db.flush()` 播种，并补了专门的回归用例 `test_a_rejected_pre_books_import_leaves_the_ledger_untouched`。
- CLI `SCHEMA_REVISION` 与四处测试里写死的版本断言一并升到 `0010`。

前端：
- 记账页顶部新增 `.ledger-book-bar` 账本切换器（含说明文案与「清除」），「管理」区最前面新增 `BookPanel` 账本面板；`EntryForm` / `BillPanel` 都能选账本（默认落在当前筛选的账本，否则第一个），流水列表在未筛选时给每行加账本标签。
- 选中账本时统计卡片改取 `/api/stats?book_id=`，与列表、报表口径一致；切账本会同时清掉账户筛选（两个筛选叠在一起会读成「没有数据」）；删掉正在筛选的账本会自动回到「全部账本」。

验证：后端 `pytest` 198 项通过（新增账本 CRUD / 越权 / 409 / 过滤、`/stats` 分账本、导入往返与旧导出兼容共 15 项），`ruff check` 与 `ruff format --check` 通过（顺手补掉 `tests/test_bookmarks.py` 遗留的格式漂移）。前端 Vitest 53 项、`vue-tsc` 类型检查、生产构建通过；**本地 Playwright 50 项（桌面 + 手机）全绿**，其中账本新增 2 条用例（建账本 → 归集流水 → 切筛选；被引用的账本只能归档不能删）。

本地 E2E 又抓到两个单测与类型检查都抓不到的问题：① 账本切换行在分区 tab **之上**，切了账本仍停在「管理」区，用例误以为会跳回「流水」；② 409 之后 `.global-error` 横幅不会自动消失，把后续用例「无全局错误」的前置检查卡住 —— 已改为显式点击「关闭错误提示」。另外 `vue-tsc` 抓到一个真实遗漏：`book_id` 只加进了 `LedgerBook`，忘了给 `Expense` / `LedgerEntry` 补字段（运行时只会是 `undefined`，静默）。

分支 CI [Actions #36236149708](https://github.com/zhigu34/digital-life/actions/runs/36236149708)（head `fb4e3d2`）与 main CI `36236546453` 的 backend / frontend / docker-e2e 三个 job 全部 success（本机 GitHub connector 无创建 PR 权限，403，故按既有授权走快进合并）。

本轮**未执行 NAS 部署**，仍由用户在合入后运行 `git pull --ff-only && ./deploy`。这次带 Alembic `0010`，`deploy` 会在迁移前自动备份旧库；`ledger_books` 是新增表、两列是纯可空列，不重建表。部署后建议在真实数据上确认三件事：旧账单与流水都落在「日常」账本下、各账户余额与升级前完全一致、切到「全部账本」时月度统计与以前相同。

## 2026-09-25 记账页筛选行折行 / 下拉空白 / 卡片右缘不对齐（`97fdacf`）

用户贴截图说「记账样式有点问题，有些没对齐，字段转行」。先把截图当测量数据用：原图 2808×1222（2× Retina）→ 反推视口 1404 CSS、页面内容宽 1282，对上 `.page{max-width:1370;padding:0 44px}`，于是本地用 1920 视口 1:1 复现，几何完全吻合。三处根因（都有浏览器实测数据），分支 `codex/ledger-layout-fix`：

1. **「账户」「月份」折成两行 + 下拉比搜索框低 7px**：工具条里的 `label`/`select` 吃到了**弹窗表单用的全局样式**（`label{margin-bottom:18px}`、`input/select/textarea{width:100%;margin-top:7px;min-width:0}`）。`margin-bottom:18px` 把筛选行撑到 57px 高、搜索框在行内居中 → 与顶部对齐的下拉错位 7px；`width:100%` + `min-width:0` 让 select 参与压缩、把 span 挤到 19.6px（不足 2 字）→ 折行。改法：`.select-field` 内的 label/select 显式 `margin:0`，select 用 `width:auto`，`span` 加 `white-space:nowrap`。注意 `.search-box` 早已写了 `margin:0`，说明同一坑踩过一次，只是 `.select-field` 漏了。
2. **统计卡片行右缘比页面右边界短 20px（宽屏）**：`.summary-card{max-width:400px}`（本是给旧的 flex 容器防过宽）落进 `grid` 后，轨道 419px 而卡片卡在 400px，每列各留 19px。只对 `.ledger-summary` / `.report-summary` 覆盖 `max-width:none`，不动仍是 flex 的 `.expense-summary`。
3. **账户下拉整块空白**（功能缺陷，非样式）：手写 `:value` + `@change` 的下拉用了 `<option :value="null">` —— Vue 会删掉该 option 的 value 属性使其回退成选项文本，而 `select` 的 DOM value 是空串 → 无匹配 → `selectedIndex = -1` → 显示空白。同款还有「记一笔」的账户选择与商户「合并到…」。改成 `value=""` + `:value="xxx ?? ''"`。注意 `v-model` 配 `:value="null"` **不受影响**（Vue 走 `option._value` 比较），所以同一页会出现「一个下拉正常、一个空白」。判定证据：`el.selectedIndex === -1`。

验证：`vue-tsc` 0 错、Vitest 50/50、构建通过、全量 E2E 38/38（含 ledger 4 项）；分支 CI `36161905500` 与 main CI `36162711157` 的 backend / frontend / docker-e2e 三 job 均 success。修复前后对照图（同数据同取景框）见 `.local/ledger-fix-compare.png`。

定位方法（截图量像素 → 反推视口/断点 → 本地 1:1 复现）已沉淀为用户级 skill `screenshot-layout-triage`。

## 2026-09-25 深色主题：画布与首帧跟随主题（`d30e58a`）

用户反馈「深色主题还是很亮」。先证明「每个亮点是谁在上色」再改色值，实测确认三条根因，分支 `codex/dark-theme-canvas`：

1. **文档画布不跟主题（主因）**：`styles.css` 的 `:root` 写的是字面值 `color: #2c3831` / `background: #f8f9f5`，而 `[data-theme="dark"]` 只覆盖 8 个自定义属性；`body` / `.app-shell` / `.main-shell` / `.page` 全透明（只有 `.topbar` 用 `var(--bg)`），所以卡片之间所有留白露出的都是永远浅色的 html 画布 —— 实测深色下 `getComputedStyle(html).backgroundColor` = `rgb(248,249,245)`，留白点逐层追祖先只有 `html` 在着色，整页像「深色卡片飘在亮米色画布上」。改为 `var(--ink)` / `var(--bg)` 并补 `color-scheme: light`；顺带修掉「未显式设色的文字继承浅色墨色、在深色卡片上暗到几乎看不见」（统计卡的数字就是）。
2. **首帧必然浅色**：主题值要等 `GET /api/auth/session` 回来才知道，而 `index.html` 没有预置脚本、也没有缓存偏好（实测 `t=32ms` 已画出暖白、`t=41ms` 才拿到 `dark`），启动屏 `.initial-loading` 自身无背景色 → **每次打开/刷新都是满屏白**。改为 `<head>` 内联脚本在样式生效前读 `localStorage['digital-life-theme']` 定主题；服务端 `user.theme` 仍是权威值，登录后由 `App.vue` 的 `theme()` 覆盖缓存。
3. **登出把主题硬设回 `light`**：`clear()` 里那句使偏好不被记住、登录页恒为浅色。改为调 `theme()` 按缓存/系统重算。

同时补齐深色块缺失的覆盖：登录页装饰（`.orbit-core` / `.orbit-chip` / `.orbit-ring`）、报错与危险操作（`.form-error` / `.global-error` / `.danger-hover` / `.button.danger-ghost`）、`.show-score` / `.show-cover img` / `.poster-thumb` / `.avatar`。`AGENTS.md` 已记录主题机制与「新增浅色字面值必须同步补深色覆盖」的约束。

验证：首帧采样 `attr` 即 `dark`、画布 `rgb(24,35,30)`；留白点上色来源只剩 `html → rgb(24,35,30)`；自写亮度扫描（面积 ≥1200px²、亮度 ≥0.62）在桌面 8 个页面跑到「无」，手机 390×844 目视无亮块；Vitest 50 项、`vue-tsc`、构建、全量 E2E 38 项全绿；分支 CI `36152037588` 与 main CI `36152953255` 的 backend / frontend / docker-e2e 三 job 均 success。

排查方法（首帧时序采样、逐点追「谁在着色」、全量亮度扫描）已沉淀为用户级 skill `dark-theme-brightness-audit`，后续改深色可直接复用。

## 2026-09-25 周期费用改造为记账模块

原「固定花销」只做推算：知道下次该付多少，但不知道钱实际从哪出、去了哪。本轮把它扩成完整的个人记账模块，分四批完成，分支 `codex/ledger`：

1. `f188d03` 后端记账域：迁移 `0008` 新建 `ledger_accounts` / `ledger_categories` / `ledger_payees` / `ledger_entries` 四表，`expenses` 增可空 `account_id` / `category_id` / `payee_id`；新增 `app/ledger/{schemas,service,router}.py`（`/api/ledger` 下账户/分类/商户/流水四组增删改查 + 商户合并 + 派生余额 + 幂等默认分类播种）；`app/main.py` 挂载；CLI 恢复版本升至 `0008`。
2. `e29e745` 账单联动：`POST /expenses/{id}/pay` 接受可选账户/分类/商户，最终生效账户非空时**在同一事务内补一条支出流水**并回传 `entry_id`；非交易类字段在推进 `next_due` **之前**校验。`/stats` 增加 `ledger_income` / `ledger_expense`（按 `occurred_on` 归集、转账排除）与 `ledger.categories` / `ledger.payees`，与既有的「推算应付」并列；导出/导入补四个记账集合（余额不导出，商户按归一化名合并，id 全量重映射，悬空引用 422）。同时抽出 `app/timezones.py` 作为 `user_today()` / `validate_timezone()` 的唯一归属地，拆掉 `records ↔ ledger ↔ maintenance` 的导入环。
3. `e074049` 前端：新增 `frontend/src/features/ledger/`（`LedgerView` 流水/账单/管理/报表四分区 + `EntryList` / `EntryForm` / `BillPanel` / `AccountPanel` / `CategoryPanel` / `PayeePanel` / `ReportPanel` / `api.ts` / `useLedger.ts` / 纯派生 `ledger.ts` / `ledger.css`）。导航项「周期费用」改名「记账」（**页面键仍是 `expenses`**，保住 `calendar.ts` 的 `kindPages` 与深链）；`CollectionView` / `RecordForm` 收窄为待办与重要日子，旧的固定花销表单与统计分支移除。
4. `2d4d20a` + `38b9fe2` + `84906c1` 修复与收尾：新增 `frontend/e2e/ledger.spec.ts`，把 `workspace.spec.ts` 里三处指向旧「周期费用」页的用例迁到记账页的「账单」分区；同步 `docs/contracts/api.md`（新增「记账」小节 + `Expense` / `/pay` / `/export` / `/import` / `/stats` 口径）、`AGENTS.md`、`README.md`。`84906c1` 另修掉一次性新建请求在导航之间残留（见下），`ledger.spec.ts` 现为 4 条用例。

**本地真实浏览器测试抓到了四个单测与类型检查都抓不到的缺陷**（`2d4d20a`、`84906c1` 修复）：

- `BillPanel.save()` 的守卫写成 `if (!editing.value) return`。`editing` 用 `null` 表示「新建」、`undefined` 表示「弹窗已关闭」，两者被混为一谈，于是**从界面添加账单永远静默失败**（提交被拦、无任何错误提示）。改为只拦 `undefined`。
- 账单确认已付会补一笔流水，但 `LedgerView` 转发 `sync` 时只更新账单快照、没有再取记账数据，导致流水页看不到这笔流水、管理页余额停在旧值。
- 账单深链一律落在记账页首屏「流水」分区：从日历点账单事件、或从今日概览的账单卡片与「查看全部账单」进入，都看不到那条账单，相对旧版属回退。改为由来源声明目标分区（`navigate(page, ledgerTab?)`，`LedgerView` 用 `startTab` 在挂载时初始化，不用 watch，避免残留状态）。
- 一次性新建请求在导航之间残留：`navigate()` 只重置起始分区、没有清零 `showCreateRequest` / `expenseCreateRequest`，而 `createFromToday` 是「先自增再导航」；视图在离开页面时被销毁（`v-else-if`），`LedgerView` 里等下一次自增的 `watch` 永远等不到，残留计数于是被重新挂载时的 `onMounted` 读到 —— 从今日概览点过一次「去记账」之后，**此后每次进入记账页都会自动弹出「记一笔」**。改为 `navigate()` 清零两个计数器、自增移到导航之后；`ShowsView` 的「添加作品」是同一写法同一症状，一并修好。

验证：本地后端 `pytest` 172 项通过、`ruff check` 与 `ruff format --check` 通过；前端 Vitest 50 项、`vue-tsc` 类型检查、生产构建通过；**Playwright 38 项（桌面 + 手机两个 viewport）全绿**。分支 CI run `36099895216`（head `38b9fe2`）与 `36119776519`（head `84906c1`）的 backend、frontend、docker-e2e 三个 job 全部 success；两次均以 `git merge --ff-only` 合入 `main` 并推送，main 上的 CI run `36100414195`（`38b9fe2`）与 `36120477546`（`84906c1`）三个 job 同样全部 success（本机 GitHub connector 无创建 PR 权限，403，故按既有授权走快进合并）。

本轮**未执行 NAS 部署**，仍由用户在合入后运行 `git pull --ff-only && ./deploy`。这次带 Alembic `0008`，部署脚本会在迁移前自动备份旧库；`expenses` 新增的三列是纯可空列、不重建表，旧数据无需处理。届时应重点在真实数据上确认：旧「固定花销」记录仍出现在记账页的「账单」分区、`/api/stats` 的 `expense_due` 数值与升级前一致（新口径只增不改）。

## 2026-09-25 V2 模块化重构的兼容层收口

`main` 已于 2026-09-17 完成 V2 模块化重构（四阶段：`codex/v2-modular-architecture`、`codex/v2-backend-shows-boundary`、`codex/v2-frontend-shows-ownership`、`codex/v2-shows-module-cleanup`，经 PR #6 合入 `6c2d711`，main CI 全绿）。该重构把追剧拆成前后端独立域，但遗留了若干只为兼容而存在的层。本轮清理这些残留并补齐文档：

- 删除 `backend/app/metadata.py` 兼容 facade（手工 re-export 20+ 符号 + `set_compat_api(sys.modules[__name__])` 反向注入，仅为保留 `app.metadata` 这个测试 monkeypatch 点）；`tests/test_metadata.py`、`tests/test_show_metadata_enrichment.py` 改为 `from app.shows import metadata as metadata_module`。
- 删除 `backend/app/shows/metadata.py` 的 `_api()` 间接层（`_compat_api` / `set_compat_api` / `_api()` 以及 `sys`、`ModuleType` 导入），所有调用点改回同模块直接调用，patch 语义不变。
- 收口 `backend/app/schemas.py` 的 Shows 惰性兼容导出（`_SHOW_SCHEMA_EXPORTS` + `__getattr__`）：`records.py` 的 `ShowView`、`imports.py` 的 `ShowPayload` 改为从 `app.shows.schemas` 直连导入；删除 `tests/test_show_service.py` 中只为兼容层存在的 legacy 导出相等断言（此后 `app.schemas` 不再暴露任何 Shows 模型，导入环随之消失）。
- `frontend/src/shows.css` 经 `git mv` 内聚到 `frontend/src/features/shows/shows.css`，`main.ts` 同步引用。
- `frontend/src/App.vue` 的 `syncShows()` 不再本地重算 `stats.shows`（与后端 `app/stats.py` 重复实现，重构期间已因此出过 bug），改为变更后请求 `GET /api/stats` 刷新；`records.shows` 仍由 feature 回传的快照更新。
- 文档同步：更新 `AGENTS.md` 代码结构章节（新增 `backend/app/shows/`、`frontend/src/features/shows/`，修正已删除的 `app/metadata.py` 引用）与模块边界约定；`docs/contracts/api.md` 补齐 Show 的 `release_year` / `completed_on` / `source_url` 字段与完成日期语义。

验证：本地后端 `pytest` 149 项通过（基线 150，减少的 1 项即随兼容层删除的 legacy 导出断言）、`ruff check` 与 `ruff format --check` 通过；前端 Vitest 40 项、`vue-tsc` 类型检查与生产构建通过。容器 E2E 与 Docker 部署场景由分支 `codex/v2-debt-cleanup` 的 GitHub CI 验证：run `36039743973`（head `3dfb752`）的 backend、frontend、docker-e2e 三个 job 全部 success。随后以 `git merge --ff-only` 合入 `main` 并推送至 `c48673e`（本机 GitHub connector 无创建 PR 权限，403 `Resource not accessible by integration`，故按既有授权走快进合并）。main 上的 CI run `36084780341`（head `c48673e`）三个 job 同样全部 success。未执行 NAS 部署，仍由用户在合入后运行 `git pull --ff-only && ./deploy`；本轮无 API、数据库或迁移变更，部署只需重建镜像。

## 2026-09-16 追剧模块独立化

追剧前端已从通用集合实现中拆出独立 `ShowsView.vue`、`ShowCard.vue`、`ShowForm.vue` 与 `shows.ts`；`CollectionView.vue` / `RecordForm.vue` 不再承载追剧专属 UI、元数据搜索或封面逻辑。后端 API、SQLite 模型和迁移均未修改，`/api/shows`、Bangumi/TMDB 元数据、poster 代理/上传与 `local:upload` 语义保持不变。实现分支 `codex/shows-module-refactor`，设计提交 `fbc4496`，主要实现/修复提交包括 `41abe2f`、`6d02206`、`4151434`、`94e2ca0`、`803795d`、`69504f9`。GitHub Actions CI #52（run `35117772201`，head `69504f9`）已验证 backend、frontend（Vitest + build）和 docker-e2e（桌面/手机 Playwright、持久化、backend-only 重部署）全部 success。执行环境无法稳定 clone GitHub，因此本轮以 GitHub Actions 作为完整验证证据；未执行 NAS 部署，仍由用户在合入 `main` 后运行 `git pull --ff-only && ./deploy`。

更新：2026-09-16。首版及周期维护功能均已合入 GitHub `main` 并由用户确认在 NAS 首次部署成功。同日多个新功能迭代已合入 `main`（快进到 `ede5949`）：统一日历、统计图表、JSON 导入、文字随记、影视元数据搜索（Bangumi），随后扩展为 Bangumi/TMDB 双信息源独立可选（含封面后端代理缓存、季数、完结/连载状态，Show 新字段 + 迁移 `0004`），以及打卡功能（每日必做/在做两类，连续与累计天数、补卡、撤销、归档，迁移 `0005`，今日总览一键打卡）。main Actions `35062580018` 与后续 TMDB 环境变量透传修复 `7924064`（main Actions `35064216310` 全绿）、打卡功能、以及移动端导航精简+独立「在做」（`codex/mobile-nav-projects`，迁移 `0006` 把 ongoing 打卡搬入 projects 且记录以文字摘要保留，main Actions `35072090920` 全绿），以及元数据诊断改进 `d6ff747`（502 详情带具体错误类与信息、后端完整堆栈日志、compose 透传 HTTP(S)_PROXY/ALL_PROXY/NO_PROXY 支持代理出网，main Actions `35074935268` 全绿；起因是用户 NAS 上 Bangumi/TMDB 均报 502。随后定位到 TMDB 报 `ConnectError: [Errno 101] Network is unreachable`（DNS 返回 AAAA 而 Docker 无 IPv6 路由），随后发现首版重试只匹配 errno 101 文案、漏了 `-9 Address family for hostname not supported`，已改为任何 ConnectError 都做一次 IPv4-only 重试（不再依赖错误文案匹配）；同分支 `8c92d2c` 还包含 deploy 优化：新增 `python -m app.cli pending-migration`，结构已是最新时跳过停服/备份/迁移，成功部署后自动把 `pre-deploy-*` 备份裁到最近 `DEPLOY_KEEP_PREDEPLOY_BACKUPS`（默认 10）份（手动备份不动；注意 set -e 下清理管道需 nullglob 保护）。main Actions `35080657599` 全绿；随后用户 NAS 在 backend 单独重建时命中 nginx 重新解析窗口导致 Web 入口校验 502 假失败，已改为自动重试约 30 秒 + nginx 连接超时收紧 3 秒 + CI 新增 backend-only 变更重部署场景（`6e16857`，main Actions `35082843510` 全绿））均已推送；NAS 待用户再次部署验证 TMDB。TMDB 真实接口因无 key 未实测（stub 单测 + E2E 已覆盖），待用户在 NAS `.env` 填写 `DIGITAL_LIFE_TMDB_API_KEY` 后实际验证。

## 用户确认的方向

- 多账号登录、各自独立生活数据。
- 待办/在办、出生天数、重要日子、固定花销、追番追剧和周期维护。
- 中文移动适配，桌面侧栏、手机底部导航，暖白绿色界面。
- Vue + FastAPI + SQLite，x86 NAS Docker；参考 camera-recorder 工程习惯。
- 本地开发、GitHub `zhigu34/digital-life`、CI、NAS `git pull --ff-only && ./deploy`。

## 已落地

- 后端账号/会话/CSRF/Origin、个人设置、管理员账号管理、原有四类记录及周期维护、独立导出、备份恢复。
- 前端全部对应页面、今日首页、主题、响应式布局、PWA 静态资源。
- 周期维护支持按天/按月周期、已过和剩余/逾期天数、提前站内提醒、完成费用与备注、历史修正及停用；每个账号独立。
- Alembic `0002` 从旧库增量增加维护事项和历史，部署前备份流程保持兼容；当前恢复严格验证 `0002` 结构、外键和同日唯一约束。
- Dockerfiles、Nginx、Compose、增量部署、在线备份/离线恢复与损坏库保全。
- GitHub Actions 后端/前端/Docker+桌面手机 E2E 工作流。
- 独立评审已修复：未改动服务停止后的恢复、Nginx 头继承、旧库迁移前备份兼容、超大整数溢出、跨浏览器时区兼容及旧资料修复。

## 已运行的验证

- 后端：97 项真实 SQLite/TestClient 测试通过；Ruff 检查和格式检查通过。
- 前端：18 项 Vitest 测试通过，类型检查和生产构建通过。
- 部署/保全脚本：9 项行为测试通过，Bash 语法检查通过。
- 已用浏览器验证本地登录和桌面/390px 手机首页视觉。
- 完整 Playwright 桌面/手机操作测试 10 项通过，新增覆盖维护创建、重复完成冲突、费用、历史修正、首页提醒、停用、刷新持久化和账号隔离。
- 独立评审发现并已修复两个 P2：删除请求中途切页导致旧卡片残留，以及恢复校验误接受部分唯一索引；两项均先以回归测试复现，再验证修复。
- 本地演示库先做 `before-maintenance.db` 备份，再由应用从 `0001` 升级到 `0002`；已有演示账号和记录保留。演示账号增加了一条“空气净化器滤芯”维护记录。
- 当前本地机器没有 Docker；真实 Linux amd64 容器已在 GitHub CI 验证通过，包含首次部署、健康检查、API/导出、桌面/手机操作、容器重建后的持久化及重复部署。
- 验证提交：`5d41173`；[GitHub Actions #34920606997](https://github.com/zhigu34/digital-life/actions/runs/34920606997) 的 backend、frontend、docker-e2e 均为 success。随后仅更新交付文档，未改应用代码。
- 周期维护验证提交：`1e3c31b`；功能分支和 [main Actions #34981612840](https://github.com/zhigu34/digital-life/actions/runs/34981612840) 的 backend、frontend、docker-e2e 均为 success。随后仅更新交付文档，未改应用代码。
- 2026-09-16 五个新功能（分支 `codex/show-metadata`，提交 `f6d556a`、`985c662`、`c27d8f5`、`b9c7bb6`、`bfd4c00`）：统一日历视图（纯前端派生 + 9 项 Vitest + E2E）；统计图表（GET /api/stats 聚合 + CSS 柱状图 + 6 项后端测试 + E2E + ci-smoke 断言）；JSON 导入（POST /api/import 整体替换 + 4 项后端测试 + E2E 真实文件流程）；文字随记（Alembic 0003 + 集合注册 + NotesView + CLI 恢复版本升至 0003 + 迁移保留测试）；动漫元数据搜索（GET /api/shows/metadata 代理 Bangumi + DIGITAL_LIFE_DISABLE_METADATA 开关 + 5 项测试 + 路由桩 E2E + 真实接口冒烟）。本地验证：后端 115 项 pytest、Ruff、前端 30 项 Vitest、构建、Playwright 20 项（桌面/手机）、make test 全部通过；浏览器实测各页面桌面与手机布局无溢出。设计/实施文档见 docs/superpowers/{specs,plans}/2026-09-16-*.md。
- deploy 完善验证提交：`17afac9`；[main Actions #35043909280](https://github.com/zhigu34/digital-life/actions/runs/35043909280) 的 backend、frontend、docker-e2e 均为 success。部署脚本参照 camera-recorder 重写：彩色输出与完整 `--help`、`--no-build`、构建错误摘要、变更文件列表、成功地址输出；部署前校验基础镜像架构与拉取、Web 端口冲突、磁盘空间与目录可写；健康检查失败状态立即终止；`DEPLOY_BUILD_VERBOSE`、`DEPLOY_AUTO_PULL`、`DEPLOY_SKIP_PORT_CHECK` 环境变量。未改动 camera-recorder 项目；未自动执行 docker prune，地址池耗尽仅提示手动处理。
- NAS 真实部署排障提交：`c7439f8`。首次部署时 backend/frontend 容器均 healthy，但「Web 入口到后端的健康检查」失败：该检查从 backend 容器内请求 `http://frontend/health`，被容器携带的出网代理（`HTTP_PROXY` 等）拦截。修复为 exec 时清空代理变量直连内网，compose 的 `NO_PROXY` 默认追加 `frontend`；另修复 `logs/deploy.log` 每次部署被清空导致失败现场丢失的问题，改为保留前一份为 `deploy.log.1`。新增 2 条回归测试，本地 19 项全部通过。

- 书签模块验证（分支 `codex/bookmarks`，提交 `87e4c6b`）：后端新增 `app/bookmarks/` 域包与 Alembic `0009`，16 项定向测试（增删改查、双账号越权、URL 伪协议与超长校验、分组与搜索过滤、访问计数、导入导出往返、内网与保留地址拒绝、功能禁用 503）；全量后端 189 项 pytest 通过。前端新增 `features/bookmarks/`，50 项 Vitest、vue-tsc 与生产构建通过；本地 Playwright 46 项（桌面/手机）全通过，其中书签 8 项覆盖添加、分组、搜索、下拉筛选（含未分组）、编辑、删除与非法协议提示。移动端在「更多」抽屉内的入口为「书签」。分支 CI [Actions #36176652551](https://github.com/zhigu34/digital-life/actions/runs/36176652551) 的 backend、frontend、docker-e2e 均为 success。标题获取是唯一新增的后端出站请求，已限制为手动触发且拒绝内网目标；站点图标由浏览器直连，后端不代理。

## 接下来

1. **本轮待用户执行**：NAS 上 `git pull --ff-only && ./deploy`，一次性拉到 `fb4e3d2`。这一跳累计包含 Alembic `0008`（记账域四表 + `expenses` 三列）、`0009`（书签表）、`0010`（`ledger_books` + 两列 `book_id`），CLI 恢复支持版本已同步升到 `0010`。`deploy` 会在迁移前自动备份旧库；三处迁移都是新增表或纯可空列，不重建既有表。部署后建议硬刷新（`Cmd/Ctrl + Shift + R`）丢掉旧 CSS 缓存，并在真实数据上确认：深色下卡片之间留白不再是米白、切主题后刷新首帧即深色；旧「固定花销」记录仍出现在记账页「账单」分区；旧账单与流水都落在「日常」账本下、各账户余额与升级前一致、切到「全部账本」时月度统计与以前相同；书签入口在侧栏底部与移动端「更多」抽屉。
2. NAS 首次部署已于 2026-09-16 由用户确认成功（用户反馈；本会话未远程连接 NAS 复核）。
3. 用户在 NAS 执行 `git pull --ff-only && ./deploy`（迁移前 deploy 会自动备份旧库）。`c7439f8` 修复了 NAS 首次部署中「Web 入口到后端的健康检查」被 backend 容器出网代理拦截的问题，重新部署即可通过；基线此前未记录，本次会重新构建并落库。累计包含 Alembic `0003`–`0008` 与新增 `DIGITAL_LIFE_DISABLE_METADATA`、`DIGITAL_LIFE_TMDB_API_KEY` 配置项；追剧元数据搜索覆盖动漫、剧集、电影（双源可选，封面后端代理）；打卡回归纯每日必做，「在做」为独立功能；移动端底部导航为 5 主入口 + 更多抽屉；「周期费用」已扩为记账模块（页面键仍为 `expenses`）。
4. 如后续通过域名公网访问，按 README 配置 HTTPS、Secure Cookie 和可信 Origin；建议先补登录失败限速和 NAS 侧自动定期备份（2026-09-16 评审提出，尚未实施，仅内网使用时可放缓）。
5. CI 的 backend job 只跑 `ruff check`，未跑 `ruff format --check`（`AGENTS.md` 要求本地两者都跑），导致 `main` 上 `app/shows/router.py`、`service.py` 长期格式漂移，已归位。建议给 CI 补上 format check，避免再次漂移。
6. `frontend/` 目前无 eslint/prettier 配置，前端写法无自动约束（`App.vue` 存在超长单行压缩写法）。若引入 lint 基线，建议单独一轮做，不要与功能改动混在同一 diff。
7. 当前没有已知阻断功能使用的问题；后续功能继续从 `main` 创建新的 `codex/` 分支。用户已授权固定交付流程：分支 CI 全绿后直接合入 `main` 推送，NAS 部署由用户执行（见 AGENTS.md 协作与交付）。

## 本地与 Git 状态提示

主开发目录就是当前仓库；本轮五个功能已合入 `main`（`438ec5b`），分支 `codex/calendar-view`、`codex/stats-charts`、`codex/json-import`、`codex/quick-notes`、`codex/show-metadata` 为其叠加链，可留档或删除。实际状态以 Git 为准。
SSH 已验证能访问 `zhigu34` 的 GitHub，远程地址使用 `git@github.com:zhigu34/digital-life.git`。没有安装 gh CLI，可使用现有 GitHub 连接器或公开 Actions API 读取状态。
本地 `.local/preview-data` 仅为本次联调使用，含测试账号，不能复制到 NAS 生产数据目录或提交。
不要依赖上一会话的进程 ID；重新检查端口是否已有服务。需要启动服务或联网时遵守当前环境权限。
