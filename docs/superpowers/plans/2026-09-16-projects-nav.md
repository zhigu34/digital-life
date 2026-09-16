# 移动端导航精简与独立「在做」Implementation Plan

**Goal:** 手机底部导航收敛为 5+更多；「在做」拆为独立 projects 功能（迁移 0006），打卡回归每日必做。
**Architecture:** projects 走 records.py 通用集合注册；0006 数据迁移把 ongoing 打卡搬进 projects 并以文字摘要保留其记录；前端 App.vue 重构移动导航（primary + more sheet），新增 ProjectsView。
**Spec:** docs/superpowers/specs/2026-09-16-projects-nav-design.md
**Constraints:** 迁移不得静默删除用户打卡记录；旧导出导入兼容；手机所有页面仍可达。

- [x] 后端：Project 模型、migrations/0006（建表 + ongoing 搬移 + 记录摘要 + 显式删子表）、cli 0006、ProjectPayload/View/Patch、COLLECTIONS 注册与导出、checkins kind 收敛为 daily、importer 支持 projects 与旧 ongoing 转换；tests/test_projects.py 3 项 + 既有断言更新（128 项全过）。
- [x] 前端：types/labels、ProjectsView、CheckInsView 去 ongoing、App.vue 移动导航重构（5 主入口 + 更多抽屉 + 遮罩 + 自动关闭）、桌面侧栏滚动与矮视口适配。
- [x] 修复（均先在测试中复现）：ProjectsView 编辑表单混入 id/created_at 致 PATCH 422（显式赋值）；E2E navigate 竞态（改为先试直连点击、兜底限定抽屉容器）；桌面 10 项侧栏把退出按钮挤出视口（侧栏可滚动 + 提示语阈值 880px）。
- [x] 验证：后端 128 项 + Ruff、前端 34 项 + 构建、Playwright 24 项（新增在做 2 项、打卡用例回归纯 daily）、make test；浏览器实测手机抽屉与在做卡片、桌面侧栏。
- [x] 文档：设计文档、本计划、api.md、README、HANDOFF；提交 codex/mobile-nav-projects 分支。

## 执行结果

本地通过：后端 128 项（新增 3 项）、前端 34 项、E2E 24 项（新增 2 项）。
