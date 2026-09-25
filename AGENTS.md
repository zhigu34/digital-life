# Digital Life — Agent 接手指南

## 项目目标与已确认约定

这是一个可在 x86 NAS 上自托管的生活工作台。用户使用独立账号登录，记录待办/在办、出生天数、纪念日、周期账单与日常记账、追番追剧。界面以中文为主，同时适配桌面和手机。

用户明确选择：**本地开发 → GitHub → CI 测试 → NAS `git pull --ff-only && ./deploy`**。仓库是 `zhigu34/digital-life`。工程部署方式参考相邻的 `camera-recorder`，但本项目独立维护；没有任务授权时不要修改那个项目。这里使用 Docker Compose 自托管，不要改成第三方网站托管。核心功能不得依赖运行时联网；唯一例外是追剧表单中用户手动触发的 Bangumi 动漫元数据搜索（`app/shows/metadata.py`，可用 `DIGITAL_LIFE_DISABLE_METADATA=true` 整体关闭），也不接入需要密钥或 AI 的外部服务。

## 新会话从哪里开始

1. 先读本文件、`README.md` 和 `docs/HANDOFF.md`。
2. 执行 `git status --short --branch`、`git log -5 --oneline`、`git remote -v`，确认真实分支、未提交改动和最新版本。不要仅凭接手文档判断代码状态，也不要覆盖用户已有改动。
3. 涉及接口时读 `docs/contracts/api.md`；整体设计及实施记录位于 `docs/superpowers/specs/`、`docs/superpowers/plans/`。
4. 优先复现问题或运行本次改动对应的测试。代码、锁文件和已运行的测试比早期设计草案更能反映当前实现。
5. 完成后更新 `docs/HANDOFF.md` 的验证结果和剩余事项，避免后续会话重复工作。不要将“计划执行”写成“已通过”。

## 代码结构

- `backend/app/main.py`：应用生命周期、来源校验、缓存头与健康检查。
- `backend/app/auth.py`、`security.py`：会话、CSRF、密码和个人设置。
- `backend/app/admin.py`：管理员创建/停用账号、重置密码。
- `backend/app/models.py`、`schemas.py`、`records.py`：数据模型、通用校验原语、通用集合（待办/账单/重要日子/随记/在做）和个人导出；账单的账户/分类/商户默认绑定与「确认已付时按需生成流水」也在 `records.py`。
- `backend/app/ledger/`：记账域独立边界。`router.py` 拥有 `/api/ledger` 下账户/分类/商户/流水四组增删改查与 `/payees/{id}/merge`；`service.py` 拥有归属查找、派生余额、引用校验（409/422）与默认分类播种；`schemas.py` 拥有记账请求/响应模型与 kind 字段组合规则。余额是派生值，没有存储余额列。
- `backend/app/timezones.py`：`user_today()` 与 `validate_timezone()` 的唯一归属地。跨域「今天」一律从这里取，避免 `records ↔ ledger ↔ maintenance` 形成导入环。
- `backend/app/shows/`：追剧域独立边界。`router.py` 拥有 `/api/shows` 增删改查与 `/advance`；`service.py` 拥有归属查找与完成日期推进规则；`schemas.py` 拥有 Show 请求/响应模型（通用 `schemas.py` 不再转发 Shows 模型）；`metadata.py` 拥有 Bangumi/TMDB 抓取、封面代理与封面上传。
- `backend/app/maintenance.py`、`maintenance_schemas.py`：周期维护、按实际日期计算的周期和带费用的完成历史。
- `backend/app/database.py`、`backend/migrations/`：SQLite 与 Alembic 迁移。
- `backend/app/cli.py`：管理员初始化、数据库迁移、一致性备份与离线恢复。
- `frontend/src/App.vue`：应用外壳（会话、导航、主题、全局通知与跨域快照），不承载具体域的增删改查。
- `frontend/src/features/shows/`：追剧域独立边界（`ShowsView`/`ShowCard`/`ShowForm`/`api.ts`/`domain.ts`/`useShows.ts`/`shows.css`），自行加载并在变更后只刷新自己，向 App 回传快照。
- `frontend/src/features/ledger/`：记账域独立边界（`LedgerView` 四分区 + `EntryList`/`EntryForm`/`BillPanel`/`AccountPanel`/`CategoryPanel`/`PayeePanel`/`ReportPanel`/`api.ts`/`useLedger.ts`/`ledger.ts` 纯派生/`ledger.css`）。账单仍由 App 的 `records.expenses` 持有，记账域通过 `sync` 回传，不触发全局 `load()`。
- `frontend/src/views/`、`components/`：其余页面与共享交互组件。
- `frontend/src/views/MaintenanceView.vue`：周期维护配置、完成与历史修正；日期由后端派生。
- `frontend/src/domain.ts`：时区、日期、周年与账单月均/应付计算；`api.ts`：Cookie/CSRF API 客户端。
- `frontend/src/styles.css`：响应式与主题；`frontend/public/`：PWA 图标、清单、静态缓存。
  主题由 `<html data-theme="light|dark">` 驱动，深色覆盖集中在 `styles.css` 末尾的 `[data-theme="dark"]` 块。`:root` 的 `color`/`background` 必须引用 `var(--ink)`/`var(--bg)`（写成字面值会让文档画布在深色下仍是浅色，卡片之间的留白全部发白）。`frontend/index.html` 的 `<head>` 内联脚本在样式生效前读 `localStorage` 里的偏好定下首帧主题，避免启动屏与登录页先闪浅色；服务端 `user.theme` 仍是权威值，登录后由 `App.vue` 的 `theme()` 覆盖缓存。组件新增浅色字面值（半透明浮层、危险色底、占位块）时，必须同步补深色覆盖。
- `deploy`、`scripts/`、`docker-compose.yml`、Dockerfiles、`frontend/nginx.conf`：NAS 运行与维护。
- `.github/workflows/ci.yml`：CI；`tests/deploy/`：部署脚本行为测试；`frontend/e2e/`：真实浏览器测试。

模块边界约定：追剧域与记账域的数据加载与变更只在各自的 `features/<域>/` 与 `app/<域>/` 内完成；App 只保留今日/日历所需的跨域快照，域内变更不再触发全局 `load()`。统计口径以服务端 `GET /api/stats` 为唯一真源，前端不得重算聚合；记账页选中单个账户时按已加载流水本地汇总属明确例外（服务端不提供按账户分组口径），该本地口径必须与全局口径可对齐。新增复杂集合时沿用同一模式（后端域包 + 前端 feature 自持数据 + 回传快照）。

## 开发环境和测试

后端 Python 3.12 + uv，前端 Node.js 22.12+（CI 使用 Node 22）+ npm。提交 `backend/uv.lock` 和 `frontend/package-lock.json`；CI 和 Docker 使用锁定安装，不随意删除锁文件。

```bash
# 根目录；完整本地单元/类型/构建/部署脚本检查
make test

# 后端单独运行
cd backend
uv sync --frozen --dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .

# 前端单独运行
cd frontend
npm ci
npm test
npm run build
```

本地启动（两个终端）：

```bash
# 终端一，backend/；首次需先使用 CLI 创建开发管理员
uv run python -m app.cli create-admin --username admin
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers

# 终端二，frontend/
npm run dev -- --host 127.0.0.1
```

开发 Web 为 `http://127.0.0.1:5173`，代理 API 到 `127.0.0.1:8000`。`DIGITAL_LIFE_DATA_DIR` 可指定独立绝对路径；服务和初始化 CLI 必须使用相同值。`.local/` 可放一次性的开发/预览数据库；不要与 NAS 正式数据混用。初始化密码使用隐藏终端输入或 CLI 专用环境变量，不能写入日志或生产默认值。

浏览器测试需先启动 API/Web，并创建专用测试管理员：

```bash
cd frontend
npx playwright install chromium
E2E_BASE_URL=http://127.0.0.1:5173 \
E2E_ADMIN_USERNAME=你的测试管理员 \
E2E_ADMIN_PASSWORD='你的测试密码' \
npm run test:e2e
```

E2E 会创建多个测试账号和生活记录；只对独立测试环境运行。它覆盖桌面和手机 viewport。Vitest 只收集 `frontend/tests/**/*.test.ts`，不能混入 Playwright 用例。

若当前机器没有 Docker，明确记录这一限制；仍应跑本地 API、浏览器和脚本测试，再在 GitHub Actions 验证容器。不要把本地单测通过等同于 Docker/NAS 已验证。

## 必须保持的业务与安全边界

- **数据归属由服务端会话确定**。所有查询、详情、统计、修改、删除、导出均按 `user_id` 限制；管理员不绕过生活数据归属。
- 新增集合或接口必须补双账号越权测试。不能相信前端隐藏、客户端提交的 `user_id` 或可猜测的 ID。
- 密码使用 Argon2 哈希；会话随机令牌只在 Cookie 中，数据库仅存其摘要。Cookie 为 HttpOnly、SameSite=Lax；HTTPS 模式使用 Secure。
- 写请求必须验证会话 CSRF 和浏览器 Origin。不要为了通过反向代理测试而关掉 CSRF、放宽到任意来源或盲信转发头。
- 登出、密码修改、管理员重置/停用、恢复备份都必须正确撤销会话；账号切换清空前端旧状态。
- 不创建公开注册/管理员抢注入口，不内置生产账号或密码。PWA 只能缓存公共静态资源，不能缓存私人 API、导出或附件。
- 金额以整数分存储，分币种统计，不做汇率换算；账户余额与记账报表一律由流水派生，不存易漂移的余额列。账单的「本月应付」（按 next_due 整周期外推的投影）与流水的「本月实际收支」（按 occurred_on 归集）是两个并列口径，不得互相替代，也不得让前端把两者相加。确认已付默认只推进下次日期；只有在账单绑定账户（或本次请求指定账户）时才在同一事务内补一条流水，并遵循「先校验、后推进日期」，校验失败不得改变 next_due。转账不计入收入与支出。
- 周期扣费保留月末 anchor，例如 1/31 → 2/28 → 3/31。出生天数使用个人时区的日历日期；闰日周年在平年按 2/28 处理。
- 时区输入须兼容浏览器 Intl，拒绝 Factory/localtime/posix/right 等系统专用名称；旧资料不能导致登录、导出或修复资料返回 500，日期显示应有 UTC 回退。
- 周期维护与固定账单语义不同：维护按最新实际完成日顺延，补录不倒退，历史修正后重新取最大完成日期。同日重复须返回409；创建自动生成首条历史，删除事项级联删除历史。
- 集数上限 1,000,000，资源 ID 限制在 SQLite 整数范围，避免通过输入校验后发生数据库溢出。

## 数据库、部署和恢复

- 使用 Alembic 增量迁移。不能通过删除数据库或 `drop_all` 解决生产迁移问题。
- **备份必须兼容旧版本数据库**：部署用新镜像在迁移前备份旧库，因此备份阶段只检查 SQLite 完整性，不能要求当前版本的精确表结构。
- 恢复需要严格验证结构/版本/完整性，并在后端停止时执行。当前备份损坏时先保全 DB/WAL/SHM 原始字节；保全或验证失败就停止，不可直接丢弃。
- 模型/迁移版本变化时同步审视 CLI 恢复支持的版本及验证逻辑。旧版本恢复需匹配代码，然后向前迁移。
- `deploy` 按内容哈希选择构建服务；构建成功前保留旧服务。后台迁移前暂停写入、做一致性备份，最后经 Web 入口验证健康才记录成功状态。
- 仅前端公开端口，默认 NAS 8090；后端 8000 只在 Docker 内网开放。Compose 需能恢复意外停止的未改动服务。
- Nginx 使用 Docker DNS 动态解析后端，避免独立更新后代理旧 IP。注意 location 内 `add_header` 会影响 server 级头继承。
- 不执行全局 Docker prune，不使用 `git reset --hard` 或删除数据目录“修复”部署。升级失败保留现场、日志、备份和真实失败退出码。
- `.env`、`data/`、`backups/`、`logs/`、`.local/`、测试报告、依赖目录均不得提交。

## 协作与交付

默认在 `codex/` 功能分支工作。用户已明确授权（2026-09-16）的交付流程：功能分支推送后 GitHub CI 全部通过，即可直接合入 `main` 并推送；NAS 部署始终由用户执行。除该流程外，不要从这份文件推断将来的合并、发布或生产操作授权。

保持中文交互、暖白/绿色的现有视觉风格、清晰表单和移动端单手操作；优先复用现有组件。新增第三方集成、共享数据、离线写入、日记图片等扩展应先确认当前任务范围。

检查改动涉及的测试，必要时加能复现问题的回归用例。核实桌面及手机布局，区分已实现、已测试和仍依赖外部环境的部分。提交前检查暂存内容，避免带上个人数据或本地运行文件。
