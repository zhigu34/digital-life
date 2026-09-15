# 周期维护设计（用户已确认）

目标：滤芯更换、清洗、保养等事项展示上次完成、已过天数、下一次到期和剩余/逾期天数。支持按天和日历月周期、提前站内提醒、完成历史、费用和备注，保持账号隔离及移动适配。

## 数据与行为

新增 maintenance 与 maintenance_logs。事项字段：id、title（1..120）、notes（<=4000）、period_value（严格整数 1..3650，months 最大 120）、period_unit（days/months）、remind_days（0..365）、active、last_completed（YYYY-MM-DD）、next_due（服务器计算）。完成记录：id、maintenance_id、completed_on、notes、cost_cents（null 或 0..100000000 严格整数）、currency（CNY/USD/EUR/JPY/HKD）、created_at。

创建事项必须提供上次完成日期，并生成对应首条历史记录。事项 PATCH 修改配置，不接受 last_completed/next_due。实际日期通过完成记录维护，last_completed 始终取历史中的最大日期。完成允许补录早于最新记录的日期，不能是用户时区的未来日期；同事项同日重复提交返回 409，不多推进周期。完成记录 PATCH 支持日期、费用、备注修正，冲突同样返回 409。首版不提供单条历史删除；删除事项经确认后级联删除其历史。

下次日期 = 最新实际完成日期 + 当前周期。按月将实际完成日的日号钳制到目标月末；如 1/31 完成，每月一次，则 2/28 到期；若 2/28 实际完成，则下一次 3/28。与固定账单的月末 anchor 不同。按天使用日历日，不受 DST 影响。服务器拒绝日期/周期计算溢出。停用事项不显示到期提醒、不可新增完成，但历史可查看/修正。

历史不单独暴露 user_id，所有路径从事项归属校验，导出包括自己事项及历史。用户时区无效旧值回退 UTC。Alembic 从 0001 升级到 0002，旧库必须先备份；恢复严格检查当前版本以及两类外键。数据库恢复测试和迁移保留旧数据测试必需。

## API

- GET/POST /api/maintenance：数组 / 创建后 201 事项。
- GET/PATCH/DELETE /api/maintenance/{id}：事项 / 200 / 204。
- GET /api/maintenance/{id}/history：按 completed_on、id 倒序的记录数组。
- POST /api/maintenance/{id}/complete：{completed_on,notes?,cost_cents?,currency?}，201 返回更新后的事项。
- PATCH /api/maintenance/{id}/history/{log_id}：完成记录部分字段，200 返回更新后的事项。
- GET /api/export：增加 maintenance 和 maintenance_logs 数组。

## 界面

独立「周期维护」页面：新增/编辑配置、卡片已使用天数与剩余/逾期、完成对话框日期/费用/币种/备注、历史列表及修正。首页显示 active 且 next_due-today <= remind_days 的事项（含逾期），跳转周期维护。手机底部导航需容纳第六项，避免横向溢出，保留现有风格。

## 验证

真实 SQLite API 覆盖双账号及管理员隔离、CSRF、重复与并发完成、补录/修正、月末/闰日/日期上界、禁用、导出、级联删除。前端纯计算测试使用个人时区日历日期。桌面/手机 E2E 验证添加、完成、历史、修正、首页提醒和账户切换隔离。GitHub CI 验证 Docker。
