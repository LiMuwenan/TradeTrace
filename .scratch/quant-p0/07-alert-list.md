---
id: 07
title: 预警列表与已读状态
status: done
blocked_by: [05]
---

## 要做什么

用户在 Web 上查看历史预警，能分辨哪些还没看过，并点开看触发时的具体情况。

## 验收标准

- [x] 预警列表按时间倒序、分页展示
- [x] 列表项展示：标的代码与名称、规则名称、触发值、阈值、数据日期、已读/未读状态
- [x] 可切换单条已读/未读；可一键全部标记已读
- [x] 可按已读状态、标的、规则类型筛选
- [x] 点击进入详情，展示触发快照：触发时指标值、阈值、使用价格、数据日期、规则参数
- [x] 详情页标注「本内容仅为数据分析，不构成投资建议」
- [x] 顶部展示未读数量

## 备注

- 已读状态是单用户全局状态，不做多用户隔离
- 同一标的同一天可能有多条不同规则的预警，列表需逐条展示
- 该页面在移动端不做，App 侧由后续票实现
- **本票不新建表**：预警即 `rule_state_event` 中 `event = 'enter'` 的行（ADR `0007-rule-state-event-stream.md`），已读是这行的 `read_at`
- **列表默认排除 `replayed = 1` 的行**（静默回放产生的历史触发），否则新规则一启用就多出上百条「预警」；「触发历史」视图才包含回放记录与 `exit` 记录

**导航**（2026-11-26 决定）：前端引入 `vue-router`，路由为 `/alerts`（列表）与 `/alerts/:id`（详情），`App.vue` 改为 `router-view`，Dashboard 侧栏增加「预警」入口并显示未读数。选它而非沿用 `ref` 切 view 的理由：详情页必须能刷新保持、能直接开链接，`ref` 方案下刷新会退回 landing。

**接口**（都在 `/api/v1` 下）：

| 路径 | 方法 | 用途 |
|---|---|---|
| `/alerts` | GET | 列表，参数 `read`(true/false/空)、`code`、`ruleType`、`page`、`pageSize`；响应含 `items`、`total`、`page`、`pageSize`、`unreadCount` |
| `/alerts/{id}` | GET | 详情快照：触发值、阈值、使用价格、数据日期，以及 `rule` 完整参数 |
| `/alerts/{id}/read` | PATCH | body `{read: bool}`，单条切换已读/未读 |
| `/alerts/read-all` | POST | 一键全部已读，返回受影响条数 |

**已读语义**（2026-11-26 决定）：进入详情**不自动**标记已读，必须显式点「已读」。理由：点开一眼又关掉是常态，自动标已读会让「稍后再处理」这条路径消失；预警的价值恰恰是「我还没看」。

**实施记录**（2026-11-26）：查询在 `app/storage/rule_store.py`（`list_alerts` / `unread_alert_count` / `get_alert` / `set_alert_read` / `mark_all_alerts_read`），组装在 `app/services/alerts.py`，路由在 `app/api/alerts.py`。前端 `AlertsPage.vue` + `AlertDetailPage.vue` + 共享顶栏 `AppShell.vue`，路由见 `web/src/router.js`。指标文案与推送正文共用一套口径（`web/src/lib/alertFormat.js` 对齐 `services/notify.py`），避免页面和手机看到两种说法。

**实施中的判断**：详情页不自动标已读（见上方「已读语义」）；`pushStateText` 只用 `pushed_at` 判断「是否已送达手机」，与已读状态互不影响——这两件事混起来会让「没收到推送」被误读成「没看过」。

**审查修正**（2026-11-26）：`get_alert` / `set_alert_read` 原先没有排除 `replayed=1`，会把回放产生的历史触发当成预警（能查详情、能标已读），与列表口径矛盾；已补 `AND replayed = 0` 与对应测试。
