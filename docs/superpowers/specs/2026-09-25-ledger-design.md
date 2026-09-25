# 记账模块设计（用户已确认范围 B）

目标：把「周期费用」从一个只做推算的账单提醒，扩展成完整的个人记账模块——能记真实发生的收入与支出、能按账户看余额、能看月度收支与分类构成。原「周期费用」不做删除，降级为记账模块里的「账单」页，继续负责周期性账单的到期提醒。

用户已确认的四项范围决策：

1. 范围 = B（账户 + 分类 + 流水 + 账单联动 + 报表），预算留作下一批。
2. 账户 = 要，多账户 + 派生余额。
3. 账单联动 = 账单**绑定账户时**「确认已付」才自动生成一笔流水；未绑定则保持原行为（只推进下次日期）。
4. 多币种 = 分币种分别汇总，不做汇率折算。

## 术语与口径（必须区分清楚，这是本模块最容易出错的地方）

| 口径 | 含义 | 数据来源 | 现状 |
|---|---|---|---|
| **推算应付** | 按账单周期外推「这个月理论上要付多少」 | `expenses` + `next_due` 外推 | 已有（`/stats` 的 `expense_due`、费用页月均成本） |
| **实际发生** | 真的花掉/收到的钱 | `ledger_entries` | **本模块新增** |

两者**都保留、都不互相覆盖**，界面上分栏展示并加文案说明，避免把推算值误读成实付值。绝不用推算值去生成流水。

### 分类 / 商户 / 备注 三者职责（不要混为一谈）

| 字段 | 回答的问题 | 形态 | 能否汇总 |
|---|---|---|---|
| 分类 | 这是**什么**开销 | 字典，可管理，收支分开 | 能（当月分类占比） |
| 商户 | 这钱花**给谁** | 字典，可管理（可归档、可合并），**可留空** | 能（当月商户 TOP） |
| 备注 | 补充说明 | 自由文本 ≤4000 | 不汇总，只参与搜索 |

流水行展示：主标题 = 备注（备注为空时退化为分类名），副标题 = `分类 · 商户`（缺哪项就省哪项）。**商户不会被塞回备注里当纯文本**——否则无法筛选与汇总。

## 数据模型（Alembic `0008`）

新增四张表（`ledger_accounts`、`ledger_categories`、`ledger_payees`、`ledger_entries`）。

### `ledger_accounts` 账户

| 字段 | 类型 | 规则 |
|---|---|---|
| id / user_id | | `Owned` 基类，归属由服务端会话决定 |
| name | String(40) | 1–40 字符 |
| kind | String(10) | `cash`/`debit`/`credit`/`ewallet`/`invest`/`other`，默认 `debit` |
| currency | String(3) | `CNY`/`USD`/`EUR`/`JPY`/`HKD`，默认 `CNY` |
| opening_balance_cents | Integer | 期初余额，整数分，允许负数（信用卡欠款），−1000000000 ~ 1000000000 |
| archived | Boolean | 默认 false；归档不删除，不再出现在新增流水的可选账户里 |
| sort_order | Integer | 默认 0，用于手动排序 |
| created_at | DateTime | 服务器时间 |

**余额为派生值，不落库**：

```
balance = opening_balance_cents
        + Σ(income.amount  where account_id = A)
        − Σ(expense.amount where account_id = A)
        − Σ(transfer.amount where from_account_id = A)
        + Σ(transfer.amount where to_account_id = A)
```

存一份余额列会产生对账不一致，明确不存。

### `ledger_categories` 分类

| 字段 | 类型 | 规则 |
|---|---|---|
| id / user_id | | 同上 |
| name | String(20) | 1–20 字符；同一用户同一 kind 下不重名（唯一约束 `uq_ledger_categories_user_kind_name`） |
| kind | String(10) | `income` / `expense`，创建后不可改（改 kind 会让历史流水语义错乱） |
| archived | Boolean | 默认 false |
| sort_order | Integer | 默认 0 |
| created_at | DateTime | 服务器时间 |

首次进入记账页且该用户没有任何分类时，服务端**幂等**创建一套默认分类（支出：餐饮/交通/居住/购物/医疗/学习/娱乐/人情/其他；收入：工资/奖金/理财/兼职/报销/其他）。判断依据是「该用户分类数为 0」，不会覆盖用户自定义。

### `ledger_payees` 商户（用户确认要做成可管理字典）

角色：回答「这钱花**给谁**」。与分类并列，但**不是**分类的子级——同一分类（餐饮）下会有多个商户（老张面馆、楼下便利店）。

| 字段 | 类型 | 规则 |
|---|---|---|
| id / user_id | | 同上 |
| name | String(40) | 1–40 字符；**存前 `strip()`**；同一用户内比较时**忽略大小写与首尾空白**，重复 409（唯一约束 `uq_ledger_payees_user_name`，比较用 `lower(name)` 归一后的值另存 `name_key` 或建函数索引，实现取其一） |
| kind | String(10) | `merchant`（默认）/ `org`（单位/机构，如宽带运营商）/ `person`（个人）——仅用于分组展示，不参与任何校验 |
| archived | Boolean | 默认 false；归档后不再出现在录入下拉里，历史流水照常显示 |
| sort_order | Integer | 默认 0 |
| created_at | DateTime | 服务器时间 |

**字典化带来的摩擦，用以下四条设计压住**（这是本表必须配套的，否则会变成负担）：

1. **录入即可新建**：记一笔表单里的商户是「可搜索下拉 + 输入不匹配可直接创建」，走同一个 `POST /api/ledger/payees`。**不需要先去 tab 里维护字典**才能记账。
2. **输入前缀匹配**：下拉按输入串对 `name` 做前缀/包含匹配，取最近使用优先排序（`sort_order` 之后按最近一条流水的日期倒序）。
3. **合并**：字典里提供「合并到…」，把来源商户的全部流水与账单改挂到目标商户，然后删除来源。防止手滑建出「老张面馆」和「老张面馆 」两条。
4. **归档即可退场**：不再去的店归档，不删除。被引用时 DELETE 一律 409（与账户、分类一致）。

### `ledger_entries` 流水

| 字段 | 类型 | 规则 |
|---|---|---|
| id / user_id | | 同上 |
| occurred_on | Date | 发生日期，YYYY-MM-DD；允许过去补录；**未来日期 422**（与周期维护完成日期一致） |
| kind | String(10) | `income` / `expense` / `transfer` |
| amount_cents | Integer | 恒为正数，1 ~ 100000000；方向由 kind 决定 |
| currency | String(3) | 必须等于所关联账户的币种，否则 422 |
| account_id | FK → ledger_accounts.id, nullable | `income`/`expense` 必填；`transfer` 必须为空 |
| from_account_id | FK → ledger_accounts.id, nullable | `transfer` 必填且与 to 不同 |
| to_account_id | FK → ledger_accounts.id, nullable | `transfer` 必填且与 from 不同 |
| category_id | FK → ledger_categories.id, nullable | `income`/`expense` 可选；`transfer` 必须为空 |
| payee_id | FK → ledger_payees.id, nullable | `income`/`expense` 可选（未标注商户时为 null，报表归入「未标注」）；`transfer` 必须为空 |
| note | Text | ≤4000，默认 '' |
| expense_id | FK → expenses.id, `ondelete=SET NULL`, nullable | 标记该流水由哪条周期账单生成 |
| created_at | DateTime | 服务器时间 |

索引：`(user_id, occurred_on)`、`expense_id`。

字段级校验规则（服务端强制，前端只是便利）：

- `kind='income'|'expense'`：`account_id` 必填，`from/to_account_id` 必须为 null；若给了 `category_id`，其 `kind` 必须与流水 kind 一致（否则 422）；`currency` 必须等于账户币种。
- `kind='transfer'`：`from_account_id`/`to_account_id` 必填且互不相同；两者币种必须相同（不折算）；`account_id`/`category_id`/`payee_id` 必须为 null；**不计入任何收支统计**，只影响两个账户的余额。
- 删除账户：被任何流水或账单引用时返回 409「该账户已有流水，请先归档」——不做级联删除，避免误删账目。
- 删除分类：被流水引用时返回 409。
- 删除商户：被流水或账单引用时返回 409；**合并**走独立动作（见接口），不靠删除。
- 删除周期账单：`expense_id` 置 null（`ondelete=SET NULL`），流水保留为普通支出。

### `expenses` 表改造（不新增表）

新增三个**可空**列：`account_id`（FK → ledger_accounts.id, nullable）、`category_id`（FK → ledger_categories.id, nullable）、`payee_id`（FK → ledger_payees.id, nullable）。
旧数据保持 null，行为与现在完全一致，不做任何历史回填（不凭空伪造流水）。`payee_id` 的作用：账单自动生成的流水能带上供应方（如「宽带费」→ 联通），参与商户汇总。

## 接口

全部挂在 `APIRouter(prefix="/api/ledger")`，归属规则与其他集合一致：所有查询/详情/修改/删除按会话 `user_id` 过滤，别人的 id 一律 404；管理员不绕过归属。

```
GET    /api/ledger/accounts              → AccountView[]（含派生 balance_cents）
POST   /api/ledger/accounts              → 201 AccountView
GET    /api/ledger/accounts/{id}         → AccountView
PATCH  /api/ledger/accounts/{id}         → AccountView
DELETE /api/ledger/accounts/{id}         → 204；被引用 409

GET    /api/ledger/categories            → CategoryView[]
POST   /api/ledger/categories            → 201；kind 重复 409
GET    /api/ledger/categories/{id}
PATCH  /api/ledger/categories/{id}       → kind 不可改
DELETE /api/ledger/categories/{id}       → 204；被引用 409

GET    /api/ledger/payees?keyword=       → PayeeView[]（`keyword` 可选，按名称包含匹配，最近使用优先）
POST   /api/ledger/payees                → 201；重名（忽略大小写与首尾空白）409
GET    /api/ledger/payees/{id}
PATCH  /api/ledger/payees/{id}           → PayeeView
DELETE /api/ledger/payees/{id}           → 204；被引用 409
POST   /api/ledger/payees/{id}/merge     → body `{into: int}`，把来源的流水与账单改挂到目标后删除来源；返回 `{entries: n, expenses: m}`

GET    /api/ledger/entries?from=&to=&kind=&account_id=&category_id=&payee_id=&limit=
POST   /api/ledger/entries               → 201
GET    /api/ledger/entries/{id}
PATCH  /api/ledger/entries/{id}
DELETE /api/ledger/entries/{id}          → 204
```

- `entries` 列表默认窗口为「最近 12 个月」（按用户时区今天回推），`from`/`to` 为可选 ISO 日期；`limit` 默认 500、上限 2000，超出上限返回 422 提示缩小范围（**不静默截断**）。排序 `occurred_on` 倒序、同日按 `id` 倒序。
- `account_id` 过滤对**转账**同样生效：一笔转账只要 `from_account_id` 或 `to_account_id` 命中即返回（它确实是该账户真实发生的一笔），但它仍不计入任何收支汇总。该参数供「按账户导出/深链」使用；流水页的账户切换在前端完成，见「界面」。
- `payee_id` 过滤只可能命中 `income`/`expense`（转账没有商户）。
- `merge` 是**同事务**操作：先把来源商户被引用的 `ledger_entries.payee_id` 与 `expenses.payee_id` 改写为目标 id，再删除来源；来源与目标都必须属于当前用户（否则 404），`into == id` 时 422。**不接受把未归档来源强行留下**——合并后来源即消失，避免留下空壳继续出现在下拉里。
- `PATCH` 的 `kind` 允许修改，但改后必须满足对应 kind 的全部字段规则（整体重校验，与 `validated_patch` 现有做法一致）。
- 请求体一律 `extra="forbid"`。

### `POST /expenses/{id}/pay` 改造（向后兼容）

请求体由「无」变为可选对象：`{occurred_on?: ISO日期, account_id?: int, category_id?: int, payee_id?: int}`（可空 body）。

行为：

1. 仍先按原逻辑推进 `next_due`（anchor_day + 整周期，短月取月底）；停用账单 400 不变。
2. 若**生效账户**存在则生成一笔流水：`kind='expense'`、`amount_cents`/`currency` 取账单的、`occurred_on` 取请求体给的日期或**用户时区今天**、`account_id`/`category_id`/`payee_id` 取请求体优先、否则回退账单上绑定的、`expense_id` 回填。账户、分类、商户的归属与 kind 校验同流水规则。
   - **生效账户** = 请求体 `account_id`，否则账单的 `account_id`。
   - 分类与商户的 id 只在**给定时**带上；账单绑定但请求体没给时用账单的；两者都没有则为 null。
3. 若**生效账户不存在**（请求体没给且账单没绑定）→ 只推进日期，不生成流水，**保持现有行为**。响应与现在结构一致，额外增加 `entry_id: int | null` 字段便于前端提示。
4. 推进日期与生成流水在**同一事务**内提交，任一步校验失败则整体回滚。

### `/stats` 扩展（不新增汇总端点）

为避免又出现「两套聚合」，记账的汇总数字**复用现有 `/stats` 管道**（与 `maintenance_cost`、`shows` 的做法一致）：

- `months[i]` 增加两个按币种汇总的整数分字段：`ledger_income`、`ledger_expense`（按 `occurred_on` 归月，窗口外不计，`transfer` 不计）。
- 新增 `ledger` 段：
  - `categories: [{category_id, name, kind, totals: {币种: 分}}]`，范围是 `end_month` **当月**，含 income 与 expense 两类；未分类流水不计入分类项。
  - `payees: [{payee_id, name, totals: {币种: 分}}]`，范围同为当月，只统计 `expense`（商户排行看花钱去处），按金额降序，取前 8；`payee_id` 为 null 的流水归入单独一项（`payee_id: null`、`name: "未标注商户"`），只有存在这类流水时才返回该项。
- 现有 `expense_due`（推算）与 `maintenance_cost` 语义与字段**不变**。

窗口、月份校验（`YYYY-MM`、非法 422）、登录要求均沿用 `/stats` 现状。

## 导出与导入

- `GET /api/export` 增加四个键：`ledger_accounts`、`ledger_categories`、`ledger_payees`、`ledger_entries`（仅当前用户）。
- `POST /api/import` 支持这四个键；旧版导出缺键按空处理（因此导入旧导出会清空记账数据，这是「整体替换」语义的预期结果，需在文档写明）。
- 导入需按现有 `checkins`/`maintenance_logs` 的做法建立 **id 映射**：`ledger_entries.account_id`/`from_account_id`/`to_account_id`/`category_id`/`payee_id`/`expense_id` 全部按映射重写；悬空引用 422、kind 与字段组合非法 422、单集合上限 10000 / 总数上限 50000 沿用。
- 导入后 `expenses.account_id`/`category_id`/`payee_id` 同样按映射重写。
- 导入商户时按**归一后的名称**去重（忽略大小写与首尾空白），同名合并为一条并让流水指向它，避免导入制造重复字典项。

## CLI 与备份恢复

- `SCHEMA_REVISION` 由 `0007` 升到 `0008`。
- 恢复校验沿用「期望表集合 = `Base.metadata.tables` ∪ {alembic_version}」的逻辑，新表自动纳入；`alembic_version` 必须等于 `0008`。
- 备份阶段仍只检查 SQLite 完整性，不要求当前版本的精确表结构（保持对旧库兼容）。

## 界面

导航项「周期费用」改名为「记账」，内部仍用页面键 `expenses`（不改键值，避免 `calendar.ts` 的 `kindPages`、深链与历史状态失效）。页面改为记账页，含四个 tab；移动端底部「更多」抽屉项数不变，标签仍为「费用」→「记账」。

```
记账页
├── 页头：本月支出 / 本月收入 / 本月结余（三张指标卡）。未选账户时标签为「本月…」且取全局口径；
│        选定单个账户后标签加账户名前缀（如「招行储蓄卡 · 本月支出」）、第三张改称「本月净流量」
├── tab 流水：筛选（全部/支出/收入/转账 + 账户 + 商户 + 月份 + 关键词）+ 按日分组列表（组头显示当日收入/支出小计）+ 每行可编辑/删除
│            「账单」来源的流水带「账单」标记 + 「由周期账单自动生成」说明
│            账户下拉选定后：列表只显示该账户流水（含以它为转出/转入方的转账），页头指标卡同步切到该账户口径，
│            并显示「已筛选：XX ✕」可一键清除；默认「全部账户」，流水页内不跨会话记忆
│            商户筛选同理（可筛选 + 显示「已筛选」），关键词同时匹配备注与商户名
├── tab 账单：原「周期费用」的全部功能原样搬过来（月均成本/本月应付摘要、近 12 个月应付趋势、确认已付、停用、固定扣费日 hint），
│            表单增加「扣款账户」「默认分类」「默认商户」三个可选项
├── tab 管理：账户 CRUD、期初余额、派生余额、归档；分类 CRUD（收支分组、改名、归档）；商户 CRUD（改名、改类型、归档、合并到…）；
│            每张账户卡带「查看流水」入口，点击后切到流水 tab 并预置该账户筛选
└── tab 报表：近 12 个月收入/支出双序列柱状图（复用现有 BarChart，不引入图表库）+ 当月分类占比（CSS 条形，非饼图）
             + 当月商户 TOP（同为 CSS 条形，取前 8）+ 当月结余
```

> tab 名由「账户」改为「管理」：里面已同时承载账户、分类、商户三块基础数据，继续叫「账户」会误导。（仅标签文字变化，不影响页面键。）

- 「记一笔」表单：类型切换（支出/收入/转账）→ 金额（数字输入，`inputmode="decimal"`）→ 账户（转账时显示转出/转入两个）→ 分类（收支按类型过滤）→ **商户（可搜索下拉，输入不匹配时下拉末尾出现「新建『XXX』」，选中即调 `POST /api/ledger/payees` 并回填）** → 日期（默认今天）→ 备注。金额以元录入、按分提交（沿用现有 `RecordForm` 的 `amount_cents` 处理方式）。转账时不显示分类与商户。
- **商户字段保持「可留空」**：不填商户的流水照常保存，报表里归入「未标注商户」。字典化不允许变成录入的强制前置动作。
- 支出用暖橙、收入用绿色、转账用中性灰，**且金额一律带 `−` / `+` 符号**，不单靠颜色区分。配色沿用现有令牌（`--green` 等），暗色主题适配。
- **账户口径的两条数字来源必须区分清楚，不能混用**：
  - 未选账户 → 页头三张卡读 App 传入的 `stats`（全局口径，真源仍是后端 `GET /api/stats`，不新增第二套全局聚合）。
  - 选定账户 → 三张卡由**已加载的流水**在前端派生（`ledger.ts` 的 `monthlySummary`），与下方列表**同源同函数**，不存在两份实现；因为 `/stats` 没有按账户维度。
  - 由此产生的不变式：**各账户当月净流量之和 = 全局当月结余**（转账不计入）。这条写成前端单测，一旦分叉就红。
  - `entries` 若因 `limit` 被截断（返回条数 `== limit`），流水页顶部显示「仅显示最近 N 笔，账户口径统计可能不完整」，不静默给出错误数字。
- 「结余」与「余额」是两个不同概念，界面上不得混称：**结余/净流量**是当月流量（收入 − 支出），**余额**是账户存量（`期初 + 累计收入 − 累计支出 ± 转账`）且只在账户 tab 出现。
- 「推算应付」与「实际发生」在账单页并排展示并各带一行说明，保持口径可辨。
- 复用现有组件：`ModalDialog`、`EmptyState`、`AppIcon`、`BarChart`、`tabs`/`search-box`/`record-list` 等既有 class，不新建视觉体系。

### 前端目录（对齐 v2 的 feature 归属范式）

```
frontend/src/features/ledger/
├── LedgerView.vue      页头 + 指标卡 + 四个 tab 的容器
├── EntryList.vue       流水分组列表 + 筛选（账户/商户筛选，选定后同步切页头指标卡口径）
├── EntryForm.vue       记一笔 / 编辑流水（含转账、商户可搜索下拉 + 输入即新建）
├── BillPanel.vue       原周期费用 UI（自 CollectionView 的 expenses 分支迁入）
├── AccountPanel.vue    账户管理（账户卡带「查看流水」跳转）
├── CategoryPanel.vue   分类管理
├── PayeePanel.vue      商户管理（改名、改类型、归档、合并到…）
├── ReportPanel.vue     收支趋势 + 分类占比 + 商户 TOP
├── ledger.ts           纯派生计算：按日分组、当月结余、单账户当月汇总（monthlySummary）、账户余额、分类占比、商户筛选谓词
├── useLedger.ts        加载与 CRUD（含商户的按需创建与合并），`emit('sync')` 回传账单快照
└── ledger.css          记账专属样式
```

- `CollectionView.vue` 移除 `expenses` 分支与其相关计算（`expenseSummary`/`expenseTrend`/`statsCurrency`），只保留 `tasks`/`milestones`。
- `domain.ts` 的 `money` / `monthlyCost` / `expenseSummary` **暂不迁移**（`TodayView` 仍在用），避免本轮 diff 扩散；后续单独一轮再做归属整理。
- 记账明细（accounts/categories/payees/entries）由 feature **懒加载**（进入记账页才请求），不进入 `App.vue` 的登录期 `Promise.all`；汇总数字从 App 传入的 `stats` 读取，与 `MaintenanceView`/`CollectionView` 的既有做法一致。

## 验证

- 后端 pytest（新增 `backend/tests/test_ledger.py`）：
  1. 双账号越权：列表/详情/PATCH/DELETE 别人 id 一律 404（账户、分类、商户、流水四类都要）。
  2. 账户 CRUD、归档；删除被流水引用的账户 409；期初余额负数（信用卡）接受、超界 422。
  3. 分类 CRUD；同用户同 kind 重名 409；改 `kind` 被拒；删除被引用 409；默认分类幂等 seed（两次进入只 seed 一次，且不覆盖自定义）。
  4. 流水校验：金额 0/超界 422、未来日期 422、`income` 挂 `expense` 分类 422、`currency` 与账户币种不符 422、`transfer` 的 from=to 422、`transfer` 带 `account_id`/`category_id`/`payee_id` 422、`transfer` 两账户币种不同 422。
  5. 余额派生：期初 + 收入 − 支出 ± 转账；转账不计入 `/stats` 的 `ledger_income`/`ledger_expense`。
  6. **商户**：CRUD 与归档；名称 `strip` 后同用户重名 409（「老张面馆」与「 老张面馆 」视为同名）、不同用户同名允许；删除被流水或账单引用 409；`merge` 把来源的流水与账单改挂目标并删除来源、返回改写条数、`into == id` 422、`into` 属于他人 404；`keyword` 查询按名称包含匹配。
  7. 账单联动：绑账户时 `pay` 生成流水且 `expense_id` 回填；未绑账户只推日期、不生成；`pay` 里显式给 `account_id` 可覆盖；停用账单 `pay` 仍 400；推进日期与生成流水同事务（分类或商户非法时日期**不**被推进）；账单绑定的 `payee_id` 会带到生成的流水上。
  8. 删除账单后流水保留且 `expense_id` 为空。
  9. `/stats`：`ledger_income`/`ledger_expense` 按 `occurred_on` 归月、按币种、窗口外不计；`ledger.categories` 仅含 `end_month` 当月、未分类不计；`ledger.payees` 只含 expense、降序前 8、`payee_id` 为 null 的归入「未标注商户」且无此类流水时不返回该项。
  10. 导出含四个新键；导入重建全部 id 映射（含 `expenses.account_id`/`category_id`/`payee_id`）与商户同名合并；旧版导出（缺键）导入不报错且把记账数据清空；悬空引用 422。
  11. 未登录 401、缺 CSRF 403、`extra` 字段 422、`limit` 超上限 422。
- 前端 Vitest（新增 `frontend/tests/ledger.test.ts`）：按日分组与当日小计、当月结余、账户余额累加（含转账方向）、分类占比排序与零值、金额正负号与格式化。
- 前端 Vitest 追加一致性与筛选用例：① 按账户筛选后列表只剩该账户流水，且**以它为转出/转入方的转账仍在列**；② 各账户当月净流量之和 === 全局当月结余（转账不计入）；③ 未选账户时页头卡走 `stats` 全局值、选定后走 `monthlySummary`，两条路径切换后数字对得上；④ 按商户筛选生效，关键词能命中商户名；⑤ 商户下拉在输入不匹配时给出「新建」项。
- Playwright + ci-smoke：记一笔支出（选商户，其中一个商户当场新建）→ 刷新后仍在 → 账户余额变化 → 在账单页确认已付 → 流水页出现带「账单」标记的记录 → 流水页选定单账户后列表只剩该账户流水、页头指标卡标签带账户名前缀 → 按商户筛选只剩该商户流水；桌面与手机 viewport。
- CI：backend / frontend / docker-e2e 三个 job 全绿后按既有流程快进合入 `main`，NAS 部署由用户执行（含 `0008` 迁移，`deploy` 会自动在迁移前备份旧库）。

## 明确不做（避免范围蔓延）

- 不做预算与超支提醒（下一批）。
- 不做汇率折算与跨币种汇总。
- 不做流水附件、发票图片、OCR。
- **不做商户的智能识别与自动归类**（不从备注猜商户、不做规则引擎、不做「导入银行账单自动匹配商户」）。
- **报表不叠加账户/商户的交叉筛选**（报表保持全局口径，筛选只作用于流水 tab），避免筛选状态跨 tab 泄漏造成误读。
- 不做周期性**收入**自动生成（只做账单→支出方向的联动）。
- 不做多用户共享账本；归属仍严格按会话用户。
- 不自动回填历史账单的流水。
