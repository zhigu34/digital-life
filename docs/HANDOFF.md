# Digital Life 接手状态

更新：2026-09-15。首版已完成并推送至 GitHub `main`，本地验证和 GitHub CI 均通过。

## 用户确认的方向

- 多账号登录、各自独立生活数据。
- 待办/在办、出生天数、重要日子、固定花销、追番追剧。
- 中文移动适配，桌面侧栏、手机底部导航，暖白绿色界面。
- Vue + FastAPI + SQLite，x86 NAS Docker；参考 camera-recorder 工程习惯。
- 本地开发、GitHub `zhigu34/digital-life`、CI、NAS `git pull --ff-only && ./deploy`。

## 已落地

- 后端账号/会话/CSRF/Origin、个人设置、管理员账号管理、四类记录 CRUD、独立导出、备份恢复。
- 前端全部对应页面、今日首页、主题、响应式布局、PWA 静态资源。
- Dockerfiles、Nginx、Compose、增量部署、在线备份/离线恢复与损坏库保全。
- GitHub Actions 后端/前端/Docker+桌面手机 E2E 工作流。
- 独立评审已修复：未改动服务停止后的恢复、Nginx 头继承、旧库迁移前备份兼容、超大整数溢出、跨浏览器时区兼容及旧资料修复。

## 已运行的验证

- 后端：55 项真实 SQLite/TestClient 测试通过，Ruff 检查通过。
- 前端：12 项 Vitest 测试通过，类型检查和生产构建通过。
- 部署/保全脚本：9 项行为测试通过，Bash 语法检查通过。
- 已用浏览器验证本地登录和桌面/390px 手机首页视觉。
- 完整 Playwright 桌面/手机操作测试 8 项通过，包含资料、记录、导出、用户切换和管理员创建账号。
- 当前本地机器没有 Docker；真实 Linux amd64 容器已在 GitHub CI 验证通过，包含首次部署、健康检查、API/导出、桌面/手机操作、容器重建后的持久化及重复部署。
- 验证提交：`5d41173`；[GitHub Actions #34920606997](https://github.com/zhigu34/digital-life/actions/runs/34920606997) 的 backend、frontend、docker-e2e 均为 success。随后仅更新交付文档，未改应用代码。

## 接下来

1. 用户在自己的 NAS 克隆仓库、执行 `./deploy`，再用 `docker compose exec backend python -m app.cli create-admin --username admin` 创建首个管理员。完整命令见 README。尚未连接或操作用户的 NAS。
2. 如通过域名访问，按 README 配置 HTTPS、Secure Cookie 和可信 Origin。
3. 后续需求在新的 `codex/` 分支开发，按改动范围运行测试并更新本文件。当前没有已知阻断首版使用的问题。

## 本地与 Git 状态提示

主开发目录就是当前仓库，首版开发分支原为 `codex/digital-life-v1`；交付时本地分支更名为 `main` 并跟踪 `origin/main`。实际状态以 Git 为准。
SSH 已验证能访问 `zhigu34` 的 GitHub，远程地址使用 `git@github.com:zhigu34/digital-life.git`。没有安装 gh CLI，可使用现有 GitHub 连接器或公开 Actions API 读取状态。
本地 `.local/preview-data` 仅为本次联调使用，含测试账号，不能复制到 NAS 生产数据目录或提交。
不要依赖上一会话的进程 ID；重新检查端口是否已有服务。需要启动服务或联网时遵守当前环境权限。
