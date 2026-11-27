---
id: 02
title: 自选清单从 watchlist.json 迁入 meta.db
status: done
blocked_by: []
---

## 要做什么

把唯一一份「用户数据放 JSON」的自选清单搬进 `meta.db`，让用户记录只落一处、备份只需一个文件。`stock_names.json` 保持文件形态（它是可重建缓存，不是用户记录）。

## 验收标准

- [x] `meta.db` 新增 `watchlist` 表：`code` 主键、`name`、`kind`（`stock`/`index`）、`added_at`、`sort_order`
- [x] 排序用 `sort_order`，不依赖秒级精度的 `added_at`
- [x] 旧 `watchlist.json` 在首次访问时导入一次，成功后改名 `watchlist.json.migrated`（保留原文件）
- [x] 迁移后清空自选**不会**从旧文件重新导入
- [x] 旧文件损坏时抛 `WatchlistCorruptError`、原文件原样保留，接口仍返回 500 +「自选文件」提示
- [x] 增删改走 `get_entry` / `upsert_entry` / `remove_entry`；`save_watchlist` 保留为整份替换
- [x] 现有自选 / 指数 / 详情测试全绿，新增迁移与存储落点测试

## 备注

- 决策与代价见 ADR `0011-watchlist-in-meta-db.md`。
- 被放弃的方案：保持 JSON（用户数据分两处、原子替换与损坏兜底全靠手写）、把 `stock_names.json` 也搬进来（缓存不是用户记录，DB 坏了名称跟着没）、迁移后删旧 JSON（没有退路）。
- 已知损失：自选不再能手改文件，要改得进 SQLite。
- 真实数据迁移已执行：`quant/data/meta/watchlist.json` → 2 条（贵州茅台 stock、沪深300 index），原文件保留为 `.migrated`。

**实施记录**（2026-11-27）：

- `_open()` 是唯一的连接入口：`connect()` 之后立刻做一次迁移检查，四个读写入口都过它，避免「某个入口忘了迁移」。
- 迁移用 `BEGIN IMMEDIATE` 包住批量插入，失败回滚且不改名文件——下次访问会重试，不会留下半份清单。
- 表里已有数据时直接忽略同名旧文件（只可能是有人手工放回来的），不覆盖已在库里的清单。
- 每个入口自开连接而不是接收连接：6 个只读调用方（自选、规则、求值、日报、个股详情、指数增量）因此零改动。
