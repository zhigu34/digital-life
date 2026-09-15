# 周期维护 Implementation Plan

**Goal:** 实现用户已确认的周期维护模块，并通过本地与 CI 验证。
**Architecture:** FastAPI 独立 maintenance 路由与两张 SQLite 表，Vue 独立页面复用现有登录、布局、对话框与 API。
**Spec:** docs/superpowers/specs/2026-09-15-maintenance-design.md
**Constraints:** 账号隔离、日期按用户时区、无外部通知服务、不改现有花销语义、向前迁移保留旧库。

- [x] 后端（backend/）：先写 tests/test_maintenance.py，POST /maintenance 预期201而当前404，验证失败；实现 models、migration0002、maintenance.py 及 schema、export、restore版本校验；覆盖月份/天数/历史/隔离/并发/迁移恢复，执行 pytest + Ruff。
- [x] 前端（frontend/src/ 与 frontend/tests/）：先验证维护剩余天数/提醒边界的失败测试；实现类型、计算、MaintenanceView、对话框和历史修正；App加载/清空/导航、Today提醒；执行 Vitest 和 build。
- [x] 集成（frontend/e2e/、scripts/ci-smoke.py）：真实浏览器分别创建每月滤芯→确认完成→查看及修正历史→重新加载→导出→账号隔离；校验桌面手机无溢出。CI持久化哨兵增加维护记录。
- [x] 独立评审迁移、隔离、日期和表单错误路径，修复后执行相关检查；更新 API文档、README、AGENTS、HANDOFF。
- [x] 提交功能分支并推送 GitHub，检查 CI 结果后交付可供 NAS 更新的 main。

## 执行结果

实现提交 `1e3c31b` 已快进到 `main`。本地 97 项后端测试、18 项前端测试、9 项部署测试和桌面/手机 10 项 E2E 通过；GitHub Actions `34981612840` 的 backend、frontend、docker-e2e 全部通过。独立评审提出的切页删除刷新及部分唯一索引恢复校验问题，均以先失败后通过的回归测试修复。
