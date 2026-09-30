# Digital Life 整体架构评估与重构方案

日期：2026-09-27
状态：设计草案（未改任何代码）
适用范围：`backend/`、`frontend/`、`docs/`、测试与工程化

## 0. 结论摘要

项目在**业务与安全边界**上很扎实（归属由会话决定、CSRF/Origin、迁移纪律、派生优先、域包模式已在 4 个域落地），真正的债集中在**三处结构性问题**：

1. **前端外壳与数据流是双轨的**：`App.vue`（93 行但单行极密）同时是路由、状态仓库、请求层、弹窗编排器；`records` 全局快照（8 键）与各 feature 自持状态并存，靠手写 `report()`/`@sync` 同步，`maintenance`/`notes` 每次保存打 9 个请求的 `load()`（`App.vue:36,81,83`）。
2. **没有路由**：`page` ref + 12 段 `v-if` 链（`App.vue:26,75-86`），无 URL 状态、无深链、无前进后退、刷新即丢上下文；13 个页面全部打进首包（`dist/assets/index-*.js` 283 KB、CSS 73.5 KB，`vite.config.ts:3-14` 无分割无别名）。
3. **样式是"原规则 + 深色 + 改版层 + 对比度层"四段叠加**：`styles.css` 3986 行里同一元素常有 2–3 处定义（`.button` 在 138/3528；表单控件在 1224/2269/3565/3803；`.tag` 在 932/2277/3581），改动成本与回归风险随功能线性上升。

后端结构比前端健康（ledger/shows/groups/bookmarks 已是 router+service+schemas 三件套），但有**两类集中风险**：`imports.py` 625 行的单体导入/导出硬编码 18 张表与 10 个域 schema（新增一个域要改 4 处）；归属查找、「409 冲突」样板、「固定条数列表查询」分别被复制 6/9/5 处，而可复用的抽象（`records.owned`）已经存在却未收敛。

## 1. 现状盘点（证据版）

### 1.1 规模

| 层 | 事实 |
|---|---|
| 后端 | `backend/app/**` 4889 行；19 张表（`app/models.py:21-292`）；11 个迁移（head `0011`）；17 个测试文件 / 142 个用例 |
| 前端 | `frontend/src/**` 13042 行；`styles.css` 3986 行占 31%；`views/` 9 个页面 2208 行；`features/` 4 个域 38 个文件；`components/` 仅 5 个（260 行） |
| 测试 | `backend/tests/` 4911 行；`frontend/tests/` 9 个纯函数用例；`frontend/e2e/` 4 个 spec 共 1247 行，其中 `workspace.spec.ts` 681 行 13 个用例 |
| 文档 | `AGENTS.md` 147 行（约定非常完整）、`docs/HANDOFF.md` 276 行、`docs/contracts/api.md` 121 行、specs 16 份、plans 16 份 |

### 1.2 前后端组织范式不一致（核心）

| 域 | 后端 | 前端 |
|---|---|---|
| ledger / shows / groups / bookmarks | `app/<域>/{router,service,schemas}.py` ✅ | `features/<域>/`（api + useXxx + 纯派生 ts + 域 css）✅ |
| records（tasks/expenses/milestones/notes/projects） | `app/records.py` 单文件混 router+service（`:58` router、`:68-180` 注册器、`:183-332` 业务），schema 寄居在共享 `app/schemas.py` | 一次性待办留在 App 的 `records.tasks` + 共享 `RecordForm`（`App.vue:78,91`） |
| maintenance | `app/maintenance.py` 单文件混（`:27` router、`:30-70` service） | `views/MaintenanceView.vue` **669 行**，自己发请求 + 自渲染弹窗，保存后 `emit("refresh")` 触发全量 `load()`（`:205,212,234,241,264`） |
| projects / notes | 走 records 注册器 | 视图直接 `api()`（`NotesView.vue:65,87`、`ProjectsView.vue:3`），App 另持列表，双写 |
| milestones / today / calendar / profile / admin | records / stats / auth / admin | 纯展示或纯自持（`AdminView` 完全自持，`ProfileView` 全 emit） |

### 1.3 前端痛点（带证据）

| # | 问题 | 证据 | 影响面 |
|---|---|---|---|
| F1 | 无路由/URL 状态 | `App.vue:26` `page=ref("today")`、`:75-86` 12 段 v-if；全仓 grep `vue-router|pushState|popstate` 0 命中 | 13 个页面、移动端返回手势、分享/刷新 |
| F2 | 外壳 6 类职责 | `App.vue:22-32`（状态）、`:33-35`(通知)、`:36`(9 并发 load)、`:39-44`(导航+跨页请求)、`:45-55`(快照+通用 CRUD)、`:60-64`(主题) | 全站唯一改动热点 |
| F3 | 数据归属双轨 + 手动同步 | 快照 `App.vue:24`；`@sync` 在 `:77,78,80`；`report()` 在 `useGroups.ts:55-57`；`syncGroups`(`App.vue:45`) 未刷新 stats 而 `syncShows/syncLedger`(`:47,48`) 刷了 | tasks/shows/ledger/maintenance/notes |
| F4 | stats 三口径 | `App.stats`(`App.vue:25`) × `LedgerView.scopedStats`(`LedgerView.vue:70-85`) × 本地汇总(`:98-100`)，违反 AGENTS「唯一真源」 | 记账/今日/追剧/维护数字 |
| F5 | 无代码分割/别名 | `vite.config.ts:3-14`（仅 vue 插件 + test + proxy）、`tsconfig.json:2-16` 无 paths、`dist/assets/` 只有 2 个产物 | 首屏体积、移动端 |
| F6 | 样式三层叠加 | `styles.css` 分段：原规则 1-2207、深色 2208-2404、响应式 2405-3494、改版层 3495-3775、对比度层 3776-3987；`features/tasks/tasks.css:413` 自带第二段改版层 | 每次视觉改动 |
| F7 | 交互复制 7–14 份 | `window.confirm` 14+ 处（`App.vue:50,52,54,55`、`BillPanel.vue:134,159`、`TasksView.vue:144,264,288` …）；搜索框 7+ 份（`ShowsView.vue:38`、`NotesView.vue:109-114`、`MaintenanceView.vue:349-367` …）；「formError + emit('save')」5 份 | 一致性、新增集合成本 |
| F8 | 测试安全网结构不良 | `workspace.spec.ts` 单文件 13 用例；`account/login/navigate` 在 4 个 spec 各复制一份（`workspace.spec.ts:8/23/31` vs `ledger.spec.ts:11/31/40` …）；4 个 `useXxx` 零单测、无组件测试 | 重构无法回归 |
| F9 | 死配置 | `Records`/`Page` 类型集中在 `types.ts:247-267`，域类型却各自定义；`styles.css:3910-3931` 的 `code/pre/mark` 无模板引用 | 轻微 |

### 1.4 后端痛点（带证据）

| # | 问题 | 证据 | 影响面 |
|---|---|---|---|
| B1 | 导入/导出单体枢纽 | `imports.py:233-625` 单函数 370+ 行；显式列 14 个模型删除（`:349-366`）；import 10 个域 schema（`:12-54`）；导出侧只有 groups 走了域函数（`records.py:275`），其余内联（`:252-331`） | 新增域要改 4 处；导入/导出正确性 |
| B2 | 归属查找重复 | `records.py:68`（`owned()` 已存在）、`ledger/service.py:42-46`、`shows/service.py:11-15`、`groups/service.py:25-31,34-41`、`bookmarks/service.py:33-39`、`maintenance.py:179-185`（内联） | 所有写路径的 404 语义 |
| B3 | 409 样板 9 处 | `ledger/router.py:83-87,111-115,227-231,255-259,320-324,349-353`、`groups/router.py:202-206`、`maintenance.py:68-70`、`admin.py:30-34` | 唯一约束冲突路径 |
| B4 | `records.py` 成跨域枢纽 | `maintenance.py:23` `from app.records import owned`；`records.py:10-17,55` 反向 import ledger/groups/shows/maintenance | 边界与循环依赖风险 |
| B5 | 索引/约束缺口 | `ledger_entries` 的 6 个 FK 列无索引（`models.py:257-271`）却按它们过滤（`ledger/service.py:168-203`）；`ledger_accounts` 无 `(user_id,name)` 唯一（`models.py:214-223`）；`shows` 无 `(user_id,source,source_id)` 唯一（`:84-101`） | 删除守卫性能、重复数据 |
| B6 | 迁移版本硬编码 5 处 | `cli.py:20` + `test_notes.py:123`、`test_groups.py:491,507`、`test_projects.py:152`、`test_maintenance_operations.py:62` | 每次迁移都要手改 |
| B7 | 契约漂移 | `PUT /api/shows/{id}/poster` 已注册（`shows/metadata.py:263-289`）但 `api.md` 无记录；`api.md:62` 仍写"封面不落库"，与 `metadata.py:288-289` 矛盾 | 契约可信度 |
| B8 | schema 归属不清 | `app/schemas.py` 同时是"共享基元"和"records 域 schema"；`ExpensePayload` 在 `schemas.py:130` 而 `ExpensePayPayload` 在 `ledger/schemas.py:120` | 新增集合时的困惑 |

### 1.5 值得保留的部分（重构中不要动）

- 归属/CSRF/Origin/Argon2/会话摘要等安全实现（`auth.py`、`security.py`）。
- 派生优先原则：余额、达标、时长、stats 都不落库。
- 域包 + 前端 feature 自持数据 + 回传快照的**思路**（问题在于同步方式，不是模式本身）。
- `timezones.py` 作为跨域「今天」的唯一叶子模块（`timezones.py:1-6` 的注释说明其必要性）。
- 迁移纪律、备份/恢复校验、部署脚本与 `tests/deploy/`（19 个用例）。
- 深色/对比度的硬约定（`AGENTS.md:45-51`）与审计脚本 `.local/dark-highlight-audit.mjs`。

## 2. 结构优化建议

### 2.1 目标：后端目录与依赖方向

```
backend/app/
  main.py                    # 只做装配：中间件 + 注册 routes + lifespan
  core/                      # 跨域基础设施（不含业务语义，可被任何域 import）
    ownership.py             # owned() 唯一实现（含 Log/子表变体）
    errors.py                # integrity_conflict()/not_found()/validate_date_range()
    collections.py           # 通用集合 CRUD 注册器（list/create/get/patch/delete）
    timezones.py             # 从 app/ 顶层移入（保持 app.timezones 再导出以免破坏 import）
    contracts.py             # 导出/导入的域插件协议
  auth.py security.py admin.py stats.py    # 保持现状（auth 的 schema 已在 schemas.py）
  schemas.py                 # 只留共享基元（Payload/ISODate/patch_schema）
  records/                   # 由 records.py 拆成包（路径 app.records 不变）
    __init__.py              # 再导出 router，兼容现有 import
    collections.py           # tasks/expenses/milestones/notes/projects 的注册
    service.py               # 通用集合业务 + /export 聚合
    schemas.py               # 从共享 schemas.py 迁入（含 ExpensePayload/ExpensePayPayload）
  maintenance/{router,service,schemas}.py  # 从 maintenance.py 拆出
  ledger/ shows/ groups/ bookmarks/        # 已有三件套，仅改 import 与共用 core
  imports.py                 # 收薄到 ~120 行：遍历域注册表
```

**依赖方向（硬规则，写入 AGENTS）**：`main → 域 → core`；`core` 不 import 任何域；域之间**只能**通过 `core` 或 services 的显式函数互相调用（禁止 `domain A → domain B` 的反向引用，特别是禁止 `core`/`maintenance` 依赖 `records`）。

**导入/导出插件化（解决 B1）**：每个域 service 暴露两个函数与一份清单：

```python
# app/ledger/service.py
EXPORT_KEY = "ledger"                      # 与旧导出 JSON 的键一致
def export_rows(db, user_id) -> dict: ...  # {"accounts": [...], "entries": [...], ...}
def import_rows(db, user_id, data: dict) -> None: ...
```

`app/imports.py` 只保留：`DOMAIN_MODELS`（删除顺序）+ 遍历 `REGISTRY`（`core/contracts.py` 的列表）。新增一个域 = 在域 service 写 2 个函数 + 在 REGISTRY 加 1 行。**格式零变化**由 golden 文件守护：`backend/tests/fixtures/export-v1.json` + 往返用例（键集合、逐域行数与样例字段都必须一致）。

**通用集合注册器（解决 B2/B3/B8）**：

```python
# app/core/collections.py
def register_collection(router, *, name, model, payload, patch, own=owned, before_write=None):
    """标准 list/create/get/patch/delete + 归属校验 + 409/422 映射，5 个简单集合共用一份实现。"""
```

`expenses` 的 `/pay`、`tasks` 的 `sync_task_completion` 通过 `before_write`/自定义路由保留（`records.py:183-332` 的既有语义不变）。

### 2.2 目标：前端目录与依赖方向

```
frontend/src/
  main.ts
  app/                       # 外壳：只做应用级关注点
    App.vue                  # <RouterView/> + 全局浮层（toast/确认框）
    router.ts                # 路由表：懒加载 + meta(title, nav, mobileTab, admin)
    session.ts               # 登录态、CSRF、账号切换（原 App.vue:22-38）
    theme.ts                 # 主题（首帧脚本 + localStorage + 服务端权威，原 :60-64）
    notify.ts                # 通知（原 :34）
    confirm.ts               # 统一确认框（替代 14 处 window.confirm）
    layout/AppShell.vue SideNav.vue MobileNav.vue MoreSheet.vue
  shared/
    api.ts                   # 唯一 fetch/CSRF/错误归一/上传（收敛 uploadPoster 的重复实现）
    types.ts                 # 只放跨域基元（Id/Date/Bill/Month），不放实体
    format.ts                # 日期/金额/时长格式化（domain.ts 的通用部分）
    ui/                      # AppIcon EmptyState ModalDialog FormDialog ConfirmDialog
                             # SearchField Toolbar ListCard StatCard SectionHeader
    styles/{layers.css,tokens.css,base.css,components.css}
  features/<域>/             # tasks shows ledger bookmarks notes projects milestones
                             # maintenance today calendar profile admin
    routes.ts                # 本域路由（懒加载）
    api.ts  types.ts  store.ts（原 useXxx）  domain.ts/periods.ts（纯派生）
    <Domain>View.vue <Domain>Detail.vue  components/
    <domain>.css             # 首行 @layer features
```

**依赖方向**：`main → app → features → shared`；`features` 之间**禁止互相 import**（需要共享就下沉到 `shared/`）；`shared` 不得 import `features`。

**数据流（单一真源，解决 F3/F4）**：

- 每个 feature 的 `store` 是该域**唯一真源**；域内增删改只动自己（`useBookmarks.visit:72-73` 的单项替换是好范例，推广到 groups/shows/ledger）。
- 删除 `App.records` 快照与 `@sync`。跨域读模型改为**服务端聚合端点**：

```
GET /api/overview?date=YYYY-MM-DD
  -> { today: {tasks[], groups[], bills[], milestones[], maintenance[]}, calendar: {...}, counts: {...} }
```

  一次请求把今日概览与日历需要的摘要算好（服务端已是唯一口径）；`features/today/store.ts` 持有它，任一域变更后只让 overview 失效重取（1 个请求，替代现在 maintenance/notes 的 9 个）。
- `stats`：保留 `/api/stats` 为唯一真源。`LedgerView` 的 `scopedStats`（`:70-85`）改为 `/api/stats?book_id=` 的同一实现分支；本地汇总（`:98-100`）删除，或改为服务端新增 `group_by=account`（二选一，见第 6 节）。

### 2.3 样式分层（解决 F6）

用 CSS `@layer` 显式声明优先级，把"四段叠加"收敛为**一处定义 + 令牌化深色**：

```css
/* shared/styles/layers.css —— 唯一声明顺序的地方 */
@layer tokens, base, components, features, overrides;
```

- `tokens.css`：`:root` 与**唯一的** `[data-theme="dark"]` 令牌块（现在散在 2208-2404 与 3502-3505）。
- `base.css`：reset、排版、元素默认、焦点环。
- `components.css`：`.button/.tag/.panel/.modal/.field` 等共享组件（改版层的样式**折叠进原规则**，删除 3495-3775 的覆写层）。
- `features/<域>.css`：域内私有样式，`@layer features`。
- `overrides` 只留"补丁"用途（如 `AGENTS.md:49` 的悬停被深色覆盖问题），且必须写明原因。

验收方式：迁移前后跑一次视觉对拍（同一份视觉稿 + `shots-*.png` 截图 diff）+ 现有 E2E 布局断言 + 深色审计脚本，做到**像素零变化**。这是纯机械迁移，但需要第 6 节的授权（与 `AGENTS.md:43` "只做覆盖、不改原规则" 的约定正面冲突）。

### 2.4 契约与文档自动化（解决 B7）

- `backend/tests/test_api_contract.py`：解析 `docs/contracts/api.md` 的 `METHOD /path`，与 `app.routes` 对比，**未记录即失败**（顺带修 `PUT /shows/{id}/poster` 与 `api.md:62`）。
- `core/contracts.py` 的 REGISTRY 生成 `api.md` 的域小节骨架（可选）。
- `SCHEMA_REVISION` 改为从 Alembic head 派生（`database.py:52,59` 已在用 `ScriptDirectory`），测试共用同一 helper（消除 B6 的 5 处硬编码）。

## 3. 各功能页面样例

### 3.0 统一的页面骨架（所有列表页共用）

```
┌ PageHeader ───────────────────────────────────────────────┐
│ eyebrow(面包屑/域)   h1 标题 + 计数       [主操作按钮]      │
│ 一句话说明（可选）                                          │
├ Toolbar ──────────────────────────────────────────────────┤
│ [SearchField] [状态/分类筛选] [排序] [视图切换]  ← URL query │
├ Content ──────────────────────────────────────────────────┤
│ 列表 / 卡片网格 / 分组折叠（EmptyState 或缺省引导）          │
├ Footer ───────────────────────────────────────────────────┤
│ 计数 / 加载更多（分页未来可加）                              │
└───────────────────────────────────────────────────────────┘
```

规则：**筛选、排序、选中项、打开的表单都进 URL query**（可分享、可后退、刷新不丢）；列表项点击进详情路由；破坏性操作用 `ConfirmDialog`（不再 `window.confirm`）；空态用 `EmptyState` + 一个主操作。

### 3.1 首页「今日概览」`/today`

| 区块 | 内容 | 数据来源 |
|---|---|---|
| 问候头 | 时段问候 + 今天是第 N 天/日期 + 时区 | `/api/overview` |
| 快捷记录 | 记录 / 待办 / 打卡 / 记账 四个入口（一键展开对应表单） | 本地 + 域 store |
| **今天的任务** | 合并原「接下来，做这些」+「今天还没打卡」①：一次性待办（可勾选完成）② 长期任务今日未打卡项（一键打卡） | `/api/overview.today` |
| 今日概览数字 | 本月支出、在看集数、下一次维护、最近记录 | `/api/overview.counts` |
| 提醒 | 周期维护到期（可点进维护页定位） | `/api/overview.maintenance` |
| 空态 | 新账号：三步引导（写第一条待办 / 记第一笔账 / 建一个长期任务） | — |

交互：一键打卡/完成是**乐观更新 + 失败回滚**（现在无乐观更新，点完要等重载）；点条目 → 域详情路由（`/tasks?item=:id`）；点"全部" → 域列表。

### 3.2 列表页样例「任务」`/tasks`

```
PageHeader  任务 [+ 添加待办] [+ 添加长期任务]        ← 两种形态永不互转
Toolbar     [搜索] [全部|待办|长期任务|已完成]  → ?view=todo|group|done
Content
  ├ 一次性待办区（CardList）：标题 + 优先级/截止 + 勾选
  └ 长期任务分组卡片：分组标题 + 本期 N/M 达标 + 打卡项行（周期格子三态 + 今日钮）
History/Log 分组展开时按需拉 /api/groups/{id}/log（保持现状）
```

导航关系：`/tasks?item=:id` 打开一次性待办编辑弹窗；`/tasks/:groupId` 进入分组详情（打卡项 + 周期格子 + 执行日志 + 组内历史）；`/today` 的打卡入口 → `/tasks?group=:g&item=:i&action=check`（消费后 `router.replace` 去掉 query）。

### 3.3 列表页样例「追剧片单」`/shows`

```
PageHeader  追剧片单 [+ 添加作品]
Stats       在看/想看/已看完/暂缓/累计看完（/api/stats）
Toolbar     [搜索] [类型: 剧集|动漫|电影] [状态] [年份]  → query
Content     按状态分组（在看→想看→已看完→暂缓），每组 card-grid
            卡片：封面（绝对定位 cover 填满，AGENTS.md:52）+ 标题 + 标签 + 进度 + [+1 集]
```

导航：点封面/标题 → `/shows/:id` 详情（封面上传、元数据搜索、进度推进、看完日期、来源链接）；`/shows?new=1` 打开新建表单。

### 3.4 列表页样例「记账」`/ledger`

```
PageHeader  记账 [+ 记一笔]
Tabs       流水 | 账单 | 账户 | 分类 | 商户 | 报表   ← /ledger/entries 等子路由
Content
  ├ 流水：按日期分组 + 每日合计 + 行内编辑
  ├ 报表：/api/stats 唯一口径（删除本地汇总）
  └ 账户/分类/商户：列表 + 合并/停用（ConfirmDialog）
```

导航：`/ledger/entries/:id` 详情；`/ledger/accounts/:id?month=` 单账户视图（服务端提供口径，取代前端本地汇总）。

### 3.5 详情页样例「分组详情」`/tasks/:groupId`（详情页范式）

桌面：右抽屉（保留列表上下文）；手机：整页 + 返回。结构：头部（分组名/归档/达标率）→ 打卡项列表（周期格子 + 明细入口）→ 执行日志（分页）→ 危险区（删除项/归档分组）。深链可直接分享/刷新恢复。

### 3.6 用户中心与设置

```
/me   个人中心   账号信息（用户名/显示名/头像字）· 主题 · 时区 · 我的数据（导出/导入）· 危险区（清空数据）
/me/security     修改密码 · 会话（当前设备/全部登出）
/admin           账户管理（管理员）：账号列表 · 创建 · 停用 · 重置密码 · 配额视图
```

导航：桌面侧栏底部两项（个人设置 / 账户管理）+ 移动端「更多」sheet；移动端底部 4 格固定为 **今日 / 日历 / 任务 / 记账**（现状已是）。

### 3.7 导航关系总图

```
AppShell
 ├ SideNav（桌面）：今日·日历·任务·在做·记账·追剧片单·重要日子·周期维护·文字随记·书签
 └ MobileNav（手机）：今日·日历·任务·记账 + 更多(Sheet：其余 + 个人设置 + 账户管理)
任何列表页 ──点击条目──> 详情路由（抽屉/整页）
今日概览 ──快捷入口──> 域表单（?new=1 / ?action=check）
详情/表单 ──保存/取消──> history.back() 或 router.replace（保持筛选 query）
```

## 4. 模块职责划分

| 模块 | 单一职责 | 允许依赖 | 明确禁止 |
|---|---|---|---|
| `app/core/ownership.py` | 归属查找与 404 | models, db | 任何域 |
| `app/core/errors.py` | HTTP 错误映射（409/422/404） | fastapi | 业务规则 |
| `app/core/collections.py` | 标准集合 CRUD 注册 | core, models | 具体域语义 |
| `app/core/contracts.py` | 导出/导入域注册表与协议 | core | 域实现细节 |
| `app/<域>/router.py` | HTTP 形状与状态码 | 本域 service, core | 其他域 |
| `app/<域>/service.py` | 本域业务规则 + 导出/导入函数 | 本域 models, core | 其他域 router |
| `app/<域>/schemas.py` | 本域请求/响应模型 | core 基元 | 其他域 schema |
| `app/imports.py` | 遍历注册表、事务边界 | core.contracts | 各域表/字段细节 |
| `app/stats.py` | 跨域只读聚合（唯一口径） | 各域 models | 写操作 |
| `shared/api.ts` | fetch/CSRF/错误归一 | — | 任何域 |
| `shared/ui/*` | 无业务语义的通用控件 | shared | features |
| `app/session.ts` `theme.ts` `notify.ts` `confirm.ts` | 应用级单例关注点 | shared | features 内部状态 |
| `app/router.ts` | 路由表与权限元信息 | features 的 routes.ts | 业务逻辑 |
| `features/<域>/store.ts` | 本域数据与变更（唯一真源） | 本域 api, shared | 其他域 store（跨域读走 overview） |
| `features/<域>/domain.ts` | 纯派生（无 Vue、可单测） | 无 | vue/api |
| `features/today/store.ts` | 跨域只读摘要 | `/api/overview` | 直接写其他域状态 |

新增一个域的模板成本（目标）：后端 3 个文件 + 2 个导出/导入函数 + 注册表 1 行；前端 `features/<域>/`（routes/api/types/store/domain + View + css）+ `router.ts` 1 行。可用 `scripts/new-domain.mjs` 生成骨架（可选，P6）。

## 5. 重构优先级

| 优先级 | 范围 | 为什么先做 | 风险/工作量 | 验收 |
|---|---|---|---|---|
| **P0 安全网** | 拆 `workspace.spec.ts` 为按域 spec + `e2e/support/fixtures.ts` 共享 `account/login/navigate`；补 `useXxx`/`FormDialog`/`ConfirmDialog` 组件与 store 单测；`test_api_contract.py` | 后面每一步都要能快速回归；现状"681 行单文件 + 4 份重复夹具 + 4 个 hook 零覆盖"无法支撑重构 | 低风险 / 中 | 用例数与覆盖不变或增加；CI 全绿 |
| **P1 前端外壳与数据流** | `App.vue` → `app/`（session/theme/notify/confirm/layout/router）；新增 `GET /api/overview`；删除 `records` 快照与 `@sync`；`stats` 口径收敛；maintenance/notes 改为自持 store | 全站唯一改动热点；消除 9 请求全量重载与三套 stats 口径（F2/F3/F4） | 中高（跨 8 个域）/ 大 | 每域"变更后不发全局 load"有测试；今日概览一次请求；数字与旧版一致 |
| **P2 路由化与代码分割** | 引入路由（见第 6 节决策），URL 化筛选/详情/表单；按路由懒加载 + `resolve.alias` | 深链/后退/刷新可用；首包从 283 KB 降到外壳+当前页（F1/F5） | 中（改所有页面入口）/ 中 | 深链与后退用例；`dist` 产物按域分块 |
| **P3 样式分层** | `layers/tokens/base/components/features`，改版层折叠回原规则，深色令牌集中 | 每次视觉改动的成本与回归风险（F6）；越晚做，叠加层越多 | 高（视觉回归）/ 中 | 截图 diff 零差异 + 深色审计 + E2E |
| **P4 共享 UI 层** | `FormDialog`/`ConfirmDialog`/`SearchField`/`Toolbar`/`ListCard`，替换 14 处 confirm、7 处搜索框、5 处表单语义 | 承载后续所有新页面；一致性与可测性（F7） | 低中 / 中 | 组件单测 + 各域迁移后行为不变 |
| **P5 后端收敛** | `core/`（owned/errors/collections/contracts）；`records`→包、`maintenance`→包；导入导出插件化 + golden 用例；索引/约束迁移 `0012`；`SCHEMA_REVISION` 单一来源 | 新增集合成本（B1/B2/B3/B4/B6）；删除守卫全表扫描（B5） | 中 / 中 | 142 个后端用例全绿 + 往返导入导出 golden + `EXPLAIN` 验证索引命中 |
| **P6 工程化收尾** | ESLint/Prettier（可选）、构建产物体积门禁、`api.md` 生成、PWA 缓存复核 | 长期卫生 | 低 / 低 | CI 门禁生效 |

推荐执行顺序：**P0 → P1 →（P5 的"core + 导入导出插件化"可与 P1 并行）→ P2 → P3 → P4 → P6**。
理由：P0 是所有后续的前置；P1/P2 是用户可感知的收益（响应速度、深链、首屏）；P3 虽然收益大但视觉风险最高，放在安全网与 P2 之后最稳；P5 与前端无耦合，可并行，且它是"新增功能成本"的根因，越早收敛越省事。

## 6. 与现有约定的冲突、需要拍板的事项

1. **引入 `vue-router`**（P2 前置，新增运行时依赖）：推荐（Vue 官方、体积 ~10 KB gzip、支持懒加载）。替代方案：自研 ~80 行 hash 路由（零依赖，但无嵌套路由/守卫，迁移成本转移到自己身上）。AGENTS.md:145 要求此类新增先确认。
2. **状态层用 Pinia 还是保持组合式函数**：推荐**不引入**——把现有 4 个 `useXxx` 抽出 `createDomainStore` 工厂，去掉 `report()` 手动同步即可；Pinia 的收益（devtools/生态）在本项目规模下不足以换一个新依赖。
3. **样式是否"折叠改版层"**（P3）：与 `AGENTS.md:43` 的"只做覆盖、回退删掉那一段即可"正面冲突。折叠后回退成本上升，但换来"一处定义"。建议保留一层 `@layer overrides` 专门给"必须靠优先级解决"的补丁（如深色悬停），其余全部折叠。
4. **新增 `GET /api/overview` 聚合端点**（P1 前置）：把跨域摘要算在服务端（唯一口径 + 1 次请求），前端不再持有 `records` 快照。替代方案：保留快照但改为"域变更只更新自己的切片 + overview 只读组合"，无需新端点、但仍有双状态。
5. **`ledger_accounts` 唯一约束**（P5）：加约束前需先扫存量同名账户；建议先加 `(user_id, name)` 唯一并在迁移中把冲突账户名加后缀，或本次只加索引。
6. **ESLint/Prettier**（P6，新增开发依赖）：现状只有 `vue-tsc`；不加也能跑，加了能防低危问题（未使用变量、缺失 key 等）。
7. **`api.md` 契约测试**是否允许 CI 因"未记录的新端点"直接失败（P0 的一部分）：推荐允许，这正是发现 B7 这类漂移的方式。

## 7. 迁移策略（渐进、不破坏现有功能）

- 每个阶段一个 `codex/` 分支，按既有交付流程（CI 全绿 → 快进合入 main → 用户执行 NAS 部署）。
- **不做大爆炸重写**：P1 期间新旧两条数据路径可以短暂并存（域 store 先接管读，再删快照）；任何阶段合入后应用都应可直接部署。
- 数据库只加索引/约束（迁移 `0012`），不动既有数据含义；导入/导出格式保持兼容（golden 用例守护）。
- 每阶段结束更新 `AGENTS.md`（依赖方向、样式分层、契约测试）与 `docs/HANDOFF.md`（验证结果）。
- 视觉相关阶段（P3/P4）必须附截图 diff 与深色审计结果。

## 8. 验收总表

| 维度 | 现在 | 目标 |
|---|---|---|
| 首包 JS | 283 KB（13 页全量） | 外壳 + 当前路由（预估 ≤120 KB） |
| 域内变更的请求数 | maintenance/notes 保存后 9 个请求 | 1 个（域内）+ 0–1 个（overview 失效重取） |
| stats 口径 | 3 套 | 1 套（`/api/stats`） |
| 同一元素的样式定义处数 | 2–3 处 | 1 处 + 令牌化深色 |
| `window.confirm` | 14+ 处 | 0（统一 ConfirmDialog） |
| 新增一个域要改的文件数 | 后端 4 处 + 前端 5 处 | 后端 1 行 + 前端 1 行（模板脚手架） |
| 未文档化的端点 | 1（PUT poster）+ 1 处过时描述 | 0（契约测试门禁） |
| 迁移版本硬编码 | 5 处 | 1 处（从 Alembic head 派生） |
| 测试 | 142 后端 + 9 单测 + 4 spec（夹具重复 4 份） | 同量级 + 共享夹具 + store/组件覆盖 |
