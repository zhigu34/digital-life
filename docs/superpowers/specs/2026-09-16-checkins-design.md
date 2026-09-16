# 打卡设计（用户已确认，2026-09-16）

目标：两类打卡项目——「每日必做」（如健身 1 小时，看连续天数）和「在做」（如项目开发，看累计天数）。支持今日一键打卡、撤销、补卡、归档与删除。

## 数据与行为

- 新表（Alembic `0005`）：`checkins`（id、user_id 级联、title 1..120、notes ≤4000、kind daily|ongoing、active、created_at）；`checkin_logs`（id、checkin_id 级联、checked_on、note ≤4000、created_at，`UNIQUE(checkin_id, checked_on)` 同日唯一）。
- 语义：
  - 打卡默认记在用户时区的"今天"；允许补录过去日期，拒绝未来日期（422）；同日重复 409；已归档项目不能打卡（400）。
  - 删除项目级联删除记录；PATCH 仅改配置（title/notes/kind/active）。
  - 连续天数在客户端按日历日计算：从今天（或昨天）往前连续计数，昨天也缺则归零；显示最近 7 天格子、本周天数、累计天数（服务端返回最近 400 天日期 + 全量计数）。
- API：`GET/POST /api/checkins`、`GET/PATCH/DELETE /api/checkins/{id}`、`GET /api/checkins/{id}/logs`、`POST /api/checkins/{id}/check`（默认今天，201 返回更新后项目含 days）、`DELETE /api/checkins/{id}/check/{checked_on}`（撤销/删某天）。全部按会话归属校验，写操作过 CSRF/Origin。
- 导出新增 `checkins`、`checkin_logs`；导入按 id 映射重建，悬空引用/同日重复/非法 kind 均 422，旧导出缺省为空。

## 界面

- 导航新增「打卡」（桌面侧栏第 4 项，手机底部导航 9 列）。
- 卡片：左侧大圆打卡钮（已打显示对勾、可撤销），标题 + 类型标签，每日必做显示"连续 N 天 · 累计 · 本周"和最近 7 天格子；在做显示"累计 N 天 · 本周 · 最近 X 天前"。操作：记录管理（补卡/查历史/删某天）、编辑、删除。
- 今日总览新增「今天还没打卡」面板，列出未完成的每日必做，一键打卡。

## 验证

- pytest：CRUD、默认今天/时区、未来 422、同日 409、撤销 404、归档 400、级联删除、导出/导入（含 0004→0005 迁移保留与版本断言）、双账号隔离。
- Vitest：shiftDate 跨月/跨年、连续天数（今天/昨天/断档）、最近 N 天、区间计数、星期标签、距上次打卡天数。
- Playwright：建每日项 → 今日页一键打卡 → 卡片连续 1 → 撤销重打 → 管理弹窗补昨天（连续 2）→ 在做项累计与"今天刚打过" → 刷新持久化 → 账号隔离 → 无横向溢出。
