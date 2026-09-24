# Digital Life 接手状态

## 2026-09-25 V2 模块化重构的兼容层收口

`main` 已于 2026-09-17 完成 V2 模块化重构（四阶段：`codex/v2-modular-architecture`、`codex/v2-backend-shows-boundary`、`codex/v2-frontend-shows-ownership`、`codex/v2-shows-module-cleanup`，经 PR #6 合入 `6c2d711`，main CI 全绿）。该重构把追剧拆成前后端独立域，但遗留了若干只为兼容而存在的层。本轮清理这些残留并补齐文档：

- 删除 `backend/app/metadata.py` 兼容 facade（手工 re-export 20+ 符号 + `set_compat_api(sys.modules[__name__])` 反向注入，仅为保留 `app.metadata` 这个测试 monkeypatch 点）；`tests/test_metadata.py`、`tests/test_show_metadata_enrichment.py` 改为 `from app.shows import metadata as metadata_module`。
- 删除 `backend/app/shows/metadata.py` 的 `_api()` 间接层（`_compat_api` / `set_compat_api` / `_api()` 以及 `sys`、`ModuleType` 导入），所有调用点改回同模块直接调用，patch 语义不变。
- 收口 `backend/app/schemas.py` 的 Shows 惰性兼容导出（`_SHOW_SCHEMA_EXPORTS` + `__getattr__`）：`records.py` 的 `ShowView`、`imports.py` 的 `ShowPayload` 改为从 `app.shows.schemas` 直连导入；删除 `tests/test_show_service.py` 中只为兼容层存在的 legacy 导出相等断言（此后 `app.schemas` 不再暴露任何 Shows 模型，导入环随之消失）。
- `frontend/src/shows.css` 经 `git mv` 内聚到 `frontend/src/features/shows/shows.css`，`main.ts` 同步引用。
- `frontend/src/App.vue` 的 `syncShows()` 不再本地重算 `stats.shows`（与后端 `app/stats.py` 重复实现，重构期间已因此出过 bug），改为变更后请求 `GET /api/stats` 刷新；`records.shows` 仍由 feature 回传的快照更新。
- 文档同步：更新 `AGENTS.md` 代码结构章节（新增 `backend/app/shows/`、`frontend/src/features/shows/`，修正已删除的 `app/metadata.py` 引用）与模块边界约定；`docs/contracts/api.md` 补齐 Show 的 `release_year` / `completed_on` / `source_url` 字段与完成日期语义。

验证：本地后端 `pytest` 149 项通过（基线 150，减少的 1 项即随兼容层删除的 legacy 导出断言）、`ruff` 通过；前端 Vitest 40 项、`vue-tsc` 类型检查与生产构建通过。容器 E2E 与 Docker 场景由分支 GitHub CI 验证（本机无 Docker）。未执行 NAS 部署，仍由用户在合入后运行 `git pull --ff-only && ./deploy`。

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

## 接下来

1. NAS 首次部署已于 2026-09-16 由用户确认成功（用户反馈；本会话未远程连接 NAS 复核）。
2. 用户在 NAS 执行 `git pull --ff-only && ./deploy`（迁移前 deploy 会自动备份旧库）。`c7439f8` 修复了 NAS 首次部署中「Web 入口到后端的健康检查」被 backend 容器出网代理拦截的问题，重新部署即可通过；基线此前未记录，本次会重新构建并落库。累计包含 Alembic `0003`–`0006` 与新增 `DIGITAL_LIFE_DISABLE_METADATA`、`DIGITAL_LIFE_TMDB_API_KEY` 配置项；追剧元数据搜索覆盖动漫、剧集、电影（双源可选，封面后端代理）；打卡回归纯每日必做，「在做」为独立功能；移动端底部导航为 5 主入口 + 更多抽屉。
3. 如后续通过域名公网访问，按 README 配置 HTTPS、Secure Cookie 和可信 Origin；建议先补登录失败限速和 NAS 侧自动定期备份（2026-09-16 评审提出，尚未实施，仅内网使用时可放缓）。
4. 当前没有已知阻断功能使用的问题；后续功能继续从 `main` 创建新的 `codex/` 分支。用户已授权固定交付流程：分支 CI 全绿后直接合入 `main` 推送，NAS 部署由用户执行（见 AGENTS.md 协作与交付）。

## 本地与 Git 状态提示

主开发目录就是当前仓库；本轮五个功能已合入 `main`（`438ec5b`），分支 `codex/calendar-view`、`codex/stats-charts`、`codex/json-import`、`codex/quick-notes`、`codex/show-metadata` 为其叠加链，可留档或删除。实际状态以 Git 为准。
SSH 已验证能访问 `zhigu34` 的 GitHub，远程地址使用 `git@github.com:zhigu34/digital-life.git`。没有安装 gh CLI，可使用现有 GitHub 连接器或公开 Actions API 读取状态。
本地 `.local/preview-data` 仅为本次联调使用，含测试账号，不能复制到 NAS 生产数据目录或提交。
不要依赖上一会话的进程 ID；重新检查端口是否已有服务。需要启动服务或联网时遵守当前环境权限。
