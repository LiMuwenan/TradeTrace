# 0011 自选清单从 JSON 文件迁入 meta.db

- 状态：已接受
- 日期：2026-11-27

## 背景

`data/meta/watchlist.json` 是「自选清单」的唯一存储：条目 `{code, name, addedAt, kind}`，靠 tmp 文件 + `os.replace` 原子替换，读时若 JSON 损坏就抛 `WatchlistCorruptError`、绝不覆盖。

同一目录下的 `meta.db` 已经是「用户记录库」，装着规则定义、触发态、通知配置与投递记录、日报快照、流水线运行记录——**同样是用户数据，却分在两个地方**。后果是备份要记得拷两个文件，且自选那份还得自己实现一遍原子替换与损坏兜底。

同时 `stock_names.json` 也在该目录，但它是**可重建缓存**（5224 条、TTL 一天、丢了下次搜索自动重拉），性质不同。

## 决策

1. **自选进 `meta.db`**：新增 `watchlist(code PRIMARY KEY, name, kind CHECK(stock|index), added_at, sort_order)`。
2. **顺序用 `sort_order` 显式列**：`added_at` 只到秒，同一秒加入两只标的时无法区分先后，不能拿它当排序键。
3. **`stock_names.json` 留在文件里**：它是外部数据的缓存，不是用户记录；进库要每次刷新整表重写 5000+ 行，还会让「DB 坏了名字也没了」。
4. **旧文件只导入一次**：表为空且 `watchlist.json` 存在时导入，成功后 `os.replace` 成 `watchlist.json.migrated`（保留原文件）。改名是必需的——否则用户清空自选后表为空，旧文件会被再次导入，删掉的标的会复活。
5. **对外函数签名基本不变**：`load_watchlist(meta_dir)` 仍是「给目录、拿清单」，新增 `get_entry` / `upsert_entry` / `remove_entry` 三个细粒度入口，`save_watchlist(meta_dir, entries)` 保留为整份替换（迁移与测试用）。调用方不需要改传连接，代价是每个入口自己开关连接。
6. **`WatchlistCorruptError` 保留**：现在只在迁移旧文件失败时抛出，语义仍是「旧文件读不了，保留原文件并报错」。

## 备选方案

| 方案 | 未采用的原因 |
|---|---|
| 保持 JSON 文件 | 用户数据分两处、备份要两份；原子替换与损坏兜底都是自己手写的，SQLite 自带 |
| 把 `stock_names.json` 也搬进库 | 缓存不是用户记录；每次刷新整表重写，且 DB 损坏时连名称也一起没 |
| 迁移后删除旧 JSON | 迁移代码出错就没有退路；`.migrated` 只占 273 B |
| 用 `added_at` 当排序键 | 秒级精度，同秒加入的两只标的顺序不稳定 |
| 把 `load_watchlist` 改成必须传 `sqlite3.Connection` | 6 个只读调用方都要跟着改，而它们本来只关心「有哪些标的」 |

## 后果

- 自选不再能手改：以前可以直接编辑 `watchlist.json` 修一条记录，现在得进 SQLite。单用户本地工具里这是实际损失，用 `sqlite3 data/meta/meta.db` 可缓解。
- 备份对象收敛为 `meta.db` 一个文件（`stock_names.json`、`index_catalog.json` 都是可重建/可种子化的）。
- 每个 `load_watchlist` 调用多一次 SQLite 连接与一条 `COUNT(*)`（迁移检查）。单次亚毫秒，但 `stock_detail`、`index_quotes` 这两个原本完全不碰 `meta.db` 的模块现在也依赖它了。
- 迁移逻辑要长期留在代码里：老用户的 `watchlist.json` 可能在任何一次升级后第一次启动时出现。
