# Digital Life 接手状态

更新：2026-09-16。首版及周期维护功能均已合入 GitHub `main` 并由用户确认在 NAS 首次部署成功。同日五个新功能迭代（统一日历、统计图表、JSON 导入、文字随记、动漫元数据搜索）已合入 `main`（快进到 `438ec5b`），main Actions `35055951580` 的 backend、frontend、docker-e2e 全部通过；NAS 待用户部署。

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

## 接下来

1. NAS 首次部署已于 2026-09-16 由用户确认成功（用户反馈；本会话未远程连接 NAS 复核）。
2. 用户在 NAS 执行 `git pull --ff-only && ./deploy`（0003 迁移前 deploy 会自动备份旧库）。本次包含 Alembic `0003` 与新增 `DIGITAL_LIFE_DISABLE_METADATA` 配置项（默认关闭，无需改动 `.env`）。
3. 如后续通过域名公网访问，按 README 配置 HTTPS、Secure Cookie 和可信 Origin；建议先补登录失败限速和 NAS 侧自动定期备份（2026-09-16 评审提出，尚未实施，仅内网使用时可放缓）。
4. 当前没有已知阻断功能使用的问题；后续功能继续从 `main` 创建新的 `codex/` 分支。用户已授权固定交付流程：分支 CI 全绿后直接合入 `main` 推送，NAS 部署由用户执行（见 AGENTS.md 协作与交付）。

## 本地与 Git 状态提示

主开发目录就是当前仓库；本轮五个功能已合入 `main`（`438ec5b`），分支 `codex/calendar-view`、`codex/stats-charts`、`codex/json-import`、`codex/quick-notes`、`codex/show-metadata` 为其叠加链，可留档或删除。实际状态以 Git 为准。
SSH 已验证能访问 `zhigu34` 的 GitHub，远程地址使用 `git@github.com:zhigu34/digital-life.git`。没有安装 gh CLI，可使用现有 GitHub 连接器或公开 Actions API 读取状态。
本地 `.local/preview-data` 仅为本次联调使用，含测试账号，不能复制到 NAS 生产数据目录或提交。
不要依赖上一会话的进程 ID；重新检查端口是否已有服务。需要启动服务或联网时遵守当前环境权限。
