# Digital Life

属于自己的生活工作台。记录待办与在办事项、出生天数、纪念日、固定花销和追番追剧进度；支持多账号独立数据、电脑与手机访问。

使用 Vue 3 + TypeScript + FastAPI + SQLite，通过 Docker Compose 部署到 NAS。前端 Nginx 统一提供 Web 和 API 入口。

## 在 x86 NAS 上部署

需要 Git、Docker Engine、Docker Compose v2、Bash，以及 sha256sum 或 shasum。首次构建需要访问容器镜像仓库、PyPI 和 npm。

```bash
git clone https://github.com/zhigu34/digital-life.git
cd digital-life
./deploy
```

脚本会生成 `.env`，默认 Web 端口为 **8090**。在浏览器打开 `http://NAS-IP:8090`。

首次部署没有默认账号。通过 NAS 终端创建管理员，密码在终端中隐藏输入：

```bash
docker compose exec backend python -m app.cli create-admin --username admin
```

密码至少 12 个字符。登录后在账号管理中为其他人创建账号。每人可以设置自己的生日、时区和主题。

后续更新：

```bash
git pull --ff-only && ./deploy
```

辅助命令：

```bash
./deploy --check-only                # 只读检查并预览部署计划
./deploy --full                      # 完整构建和部署
./deploy --no-build                  # 跳过镜像构建，仅更新容器（不记录部署基线）
./deploy --help                      # 查看全部选项

docker compose ps
docker compose logs -f --tail=100
```

脚本根据源文件内容判断受影响服务：只改前端就只重建前端。构建前会检查并按需拉取基础镜像、校验架构匹配、检测 Web 端口冲突和磁盘空间；构建完成后才停止需要更新的后端；迁移前制作数据库一致性备份。Web 和后端健康检查都通过后才记录成功版本。

离线或受限环境可用环境变量调整行为：`DEPLOY_AUTO_PULL=0` 在缺少基础镜像时不自动拉取（改为提示用 `docker save`/`docker load` 导入）、`DEPLOY_SKIP_PORT_CHECK=1` 跳过端口冲突检测、`DEPLOY_BUILD_VERBOSE=1` 显示完整构建输出。

`.env`、`data/`、`backups/` 和 `logs/` 留在 NAS，不会通过 Git 同步。更新不会重置密码或删除记录。部署锁位于 `logs/deploy.lock`；异常断电遗留锁时，先确认没有部署或备份/恢复进程，再手动移除该空目录。

## 手机与 HTTPS

手机和电脑使用同一网址、同一账号。手机界面采用底部导航和单列卡片；在支持的浏览器中可以添加到主屏幕。

PWA 安装需要 HTTPS（localhost 开发环境例外）。在 NAS 反向代理中为自己的域名配置 HTTPS，代理到本机 8090 端口，然后修改 `.env`：

```dotenv
DIGITAL_LIFE_SECURE_COOKIE=true
DIGITAL_LIFE_TRUSTED_ORIGINS=https://life.example.com
```

运行 `./deploy` 应用配置。Origin 必须包含协议和实际端口，不能填写路径或通配符。多个可信入口使用逗号分隔。启用 Secure Cookie 后使用 HTTPS 登录；HTTP 页面无法使用该登录 Cookie。

第一版需要联网访问 NAS；PWA 不提供离线编辑或后台推送。私人 API 数据不会保存在离线缓存中。

## 本地开发

需要 Python 3.12、uv 和 Node.js 22.12+（推荐 Node 22）。在两个终端中分别运行后端和前端。

```bash
# 终端一
cd backend
uv sync --frozen --dev
uv run python -m app.cli create-admin --username admin
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers
```

```bash
# 终端二
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

访问 `http://127.0.0.1:5173`，Vite 会代理 `/api` 到本地后端。默认开发数据库位于项目 `data/`；建议使用专门的开发账号。也可设置 `DIGITAL_LIFE_DATA_DIR` 为独立绝对路径，CLI 和服务必须使用相同路径。

## 测试和 CI

```bash
make test

# 真实浏览器测试：先启动 Web/API，并创建测试管理员
cd frontend
npx playwright install chromium
E2E_BASE_URL=http://127.0.0.1:5173 \
E2E_ADMIN_USERNAME=admin \
E2E_ADMIN_PASSWORD='你的测试管理员密码' \
npm run test:e2e
```

浏览器测试会创建独立的测试账号和业务记录，请使用开发环境。

GitHub Actions 在每次 push 和 PR 时执行：

- 后端测试与代码检查：账号隔离、会话撤销、业务边界、备份恢复。
- 前端测试、类型检查和生产构建。
- 部署脚本行为测试：增量构建、失败处理、成功状态记录。
- Linux amd64 容器部署、真实桌面/手机浏览器流程，以及容器重建后的数据保留。

日常建议在功能分支开发，经 PR 的 CI 验证后合入 `main`。请在 GitHub 仓库设置中把 CI 设为合并必要条件；仅提交 workflow 不会自动启用分支保护。

## 备份与恢复

随时制作在线一致性备份：

```bash
./scripts/backup
```

备份输出到 `backups/`。这份数据库包含所有账号的数据，应与 `.env` 一起妥善保管，定期复制到独立存储。用户也可以在界面导出自己的 JSON 记录；个人 JSON 导出不等同于可恢复的整站数据库备份。

恢复会替换整站数据并撤销备份中的会话。脚本先停后端、保存当前数据库，再恢复所选文件：

```bash
./scripts/restore --confirm backups/manual-YYYYMMDDTHHMMSSZ-进程号.db
./deploy
```

如果当前数据库已经损坏、无法制作有效备份，恢复脚本会先把数据库及 WAL/SHM 原始文件完整复制到 `backups/damaged-current-时间戳/`；原始文件保全失败就停止恢复。所选恢复文件仍必须通过结构和完整性校验。恢复失败时后端保持停止，请检查错误后再操作。升级迁移后的代码回退需要匹配旧代码和迁移前备份；仅 `git checkout` 旧提交不能撤销数据库迁移。切换代码前确认当前修改已保存。不要直接复制仍在写入的 SQLite 主文件作为备份，也不要对 NAS 执行删除数据目录或全局 Docker 清理来解决升级失败。

## 第一版范围

- 多账号登录、管理员创建/停用账号与重置密码。
- 今日总览、事项列表、状态与优先级、截止日期。
- 统一日历：一张月历集中查看待办截止、周期扣费、维护到期和重要日子。
- 出生天数、纪念日与年度倒计时。
- 月/季/年固定花销、月均成本与本月应付分开、确认本期已付。
- 追番追剧状态、集数进度、评分和备注。
- 周期维护：滤芯、清洗、保养的已过天数、下次到期、站内提醒和带费用备注的完成历史。
- 统计图表：近 12 个月应付趋势、维护费用汇总和追剧统计，轻量柱状图无需图表库。
- 个人资料、主题、时区、密码修改与个人 JSON 导出。

花销的“确认本期已付”推进下一扣费日，第一版不保存历史银行流水。番剧信息手动维护。日记照片、自动内容同步、外部提醒和离线编辑属于后续扩展。

各账号的数据访问在服务端校验。管理员在界面中没有读取他人生活记录的特权，但具有 NAS 文件权限的部署者仍能读取底层数据库。

## 日历怎么用

打开「日历」即可看到当月月历：待办截止、周期费用扣费日、维护到期和重要日子以不同颜色标注在同一格里，点某一天可在下方查看当日安排，点安排可直达对应页面。周期费用按整周期从下次应付日外推（未确认支付也会显示未来扣费日，且保留月末 anchor），每年重复的重要日子每年都会出现，闰日在平年按 2 月 28 日显示。

## 周期维护怎么用

打开「周期维护」→「添加维护」，填写名称、上次完成日期、周期和提前提醒天数。例如净水器滤芯每 6 个月更换、提前 14 天提醒。卡片显示已过天数、下次到期和剩余/逾期天数，临近到期与逾期事项会出现在「今日总览」。

完成后点「记录完成」，确认实际日期，可填写费用与备注。「查看历史」可以检查和修正过去的记录。按天与按日历月分开计算，周期从最新实际完成日期顺延；例如 1 月 31 日完成、周期 1 个月，则 2 月末到期，若 2 月 28 日实际完成，下一次是 3 月 28 日。补录更早记录不改变最新周期，同日重复会提示冲突。

编辑事项可调整周期、提醒、备注或停用。停用后不再显示提醒，也不能新增完成记录，但历史仍可查看和修正。删除事项会同时删除它的完成历史。提醒目前仅显示在工作台内。

本功能通过 Alembic `0002` 新增数据表，`./deploy` 会先备份旧库再升级，不需要重建数据库。当前版本的整站恢复只接受 `0002` 数据库；若需要恢复升级前的 `0001` 备份，先切回与备份匹配的应用版本执行恢复，再更新并迁移。

## 其他开发会话接手

先阅读 [AGENTS.md](AGENTS.md) 的工程约定与维护边界，再查看 [docs/HANDOFF.md](docs/HANDOFF.md) 的实际验证结果和剩余事项。接口约定见 [docs/contracts/api.md](docs/contracts/api.md)。
