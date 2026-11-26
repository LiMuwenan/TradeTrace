---
id: 13
title: 日报投递失败后的补投
status: todo
blocked_by: []
---

## 要做什么

09 号票（日报）与 10 号票（调度）已经上线，但「日报生成成功、投递失败」这一种情况目前会静默丢失：流水线把日报阶段记成 `ok`，游标照常前进，当天再也不会自动重投。本票决定这种情况怎么补，并把它实现出来。

## 现状（代码事实）

- `app/services/report.py:generate` 在三种情况下返回 `delivered: False`，且都不写 `daily_report.pushed_at`：
  1. 通知通道未配置（`reason: 通知通道尚未配置`）；
  2. `send_report` 抛异常（`reason` 为异常消息）；
  3. `send_report` 返回 `ok=False`（ntfy 与邮件都失败，`reason` 为 `outcome.error`）。
- `app/services/pipeline.py:run` 只要 `generate` 没抛异常，就把 `report` 阶段记为 `ok`，detail 写「未投递：<原因>」，然后**照常** `advance_cursor`。
- `app/services/pipeline.py:catch_up` 找缺口只看两处：游标之后的**工作日**，以及运行记录里 `status='failed'` 的日期。日报没投递既不是工作日缺口，也不是 failed，所以永远不会被重跑。
- 结果：那天用户既没收到逐条预警（如果推送也失败）也没收到日报，而 Web 上的运行记录是一排绿勾。「日报负责不漏」的兜底静默失效。

## 需要定的事

1. **阶段状态怎么记**。记 `failed` 会让游标不前进，次日 `catch_up` 重跑该日（求值与日报都幂等），但永久性失败（例如通道一直没配）会让游标卡住，最多积压 `MAX_CATCH_UP_DAYS = 10` 天。记 `ok` 则必须另找补投机制。二者选一，不能两头都不做。
2. **补投的触发方式**：定时任务的每日补跑顺带处理，还是只留手动入口。
3. **是否重算正文**。09 已定「已投递不改写」，未投递允许覆盖草稿，因此重投可以重算；但重算会让 `nearMisses` 等字段与当天首次生成时不同，需要在票面写清取哪一份。
4. **防重复投递**。任何补投路径都必须以 `pushed_at` 为准做幂等：已写 `pushed_at` 的日期一律不再发。

## 验收标准

- [ ] 通道正常情况下，某日日报投递失败后，能在不改数据的前提下补投一次，且只补投这一件事（不重复取数、不重复推送预警）
- [ ] 同一交易日的日报不会被投递两次
- [ ] 投递失败在运行记录里一眼可见，不需要点开 detail 才知道「这天其实没发出去」
- [ ] 通道长期未配置时，流水线不会被这一天的日报拖住，后续交易日照常推进
- [ ] 补投后 `daily_report.pushed_at` 与 `push_channel` 正确落库

## 备注

发现于 10 号票上线后的双轴审查（Spec 轴，条款 09「每个交易日生成一份日报」与 10「失败原因可见」）。相关代码：`app/services/report.py`、`app/services/pipeline.py`、`app/storage/report_store.py`。
