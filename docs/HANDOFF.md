# Digital Life 接手状态

更新：2026-09-15。首版及周期维护功能均已合入 GitHub `main`，本地验证和 GitHub CI 均通过。

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

## 接下来

1. 用户在 NAS 运行 `git pull --ff-only && ./deploy`。脚本会在 `0002` 迁移前备份旧库；尚未连接或操作用户的 NAS。
2. 如通过域名访问，按 README 配置 HTTPS、Secure Cookie 和可信 Origin。
3. 当前没有已知阻断周期维护功能使用的问题；后续功能继续从 `main` 创建新的 `codex/` 分支。

## 本地与 Git 状态提示

主开发目录就是当前仓库，当前分支为 `main` 并跟踪 `origin/main`；周期维护实现提交为 `1e3c31b`。实际状态以 Git 为准。
SSH 已验证能访问 `zhigu34` 的 GitHub，远程地址使用 `git@github.com:zhigu34/digital-life.git`。没有安装 gh CLI，可使用现有 GitHub 连接器或公开 Actions API 读取状态。
本地 `.local/preview-data` 仅为本次联调使用，含测试账号，不能复制到 NAS 生产数据目录或提交。
不要依赖上一会话的进程 ID；重新检查端口是否已有服务。需要启动服务或联网时遵守当前环境权限。
