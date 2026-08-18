# CLAUDE.md

本文件提供 `EverythingTool` 项目的详细架构与规范。**行为规则的权威版本在 `AGENTS.md`，两者冲突时以 `AGENTS.md` 为准。**；本文件重点展开代码设计与数据库，供修改前快速对齐。

> 提示：新增工具时，把「作为 Agent 的注意事项」写进 `AGENTS.md`，把「架构/代码设计细节」写进本文件。

## 项目概览

- **类型**：Flutter 桌面优先的个人工具集 App（Windows 目标验证）。
- **名称**：`EverythingTool`（package 名 `everything_tool`）。
- **入口**：`lib/main.dart`，`main()` 内做 `sqfliteFfiInit()` 与 `databaseFactory = databaseFactoryFfi`。
- **主题**：Material 3，`colorSchemeSeed: Colors.blue`。

## 当前工具与存储映射

数据存储使用SQLite `stock_trading.db` WebDAV 整库上传/下载

## 数据库设计（SQLite，`DatabaseHelper` 维护）

库文件：`{设备id}/stock_trading.db`。Windows 依赖 FFI。

### 表结构


**t_password_account**（密码管理模块的单条密码记录）
```
id TEXT PRIMARY KEY,app_name TEXT NOT NULL,username TEXT NOT NULL,
password TEXT NOT NULL,created_at TEXT NOT NULL
```

**t_accounts**（证券账户）
```
id INTEGER PK AUTOINCREMENT, name TEXT, created_at TEXT
```

**t_stocks**（账户下的股票）
```
id PK, account_id FK→t_accounts(id) ON DELETE CASCADE,
name TEXT, code TEXT, created_at TEXT
```

**t_transaction_trades**（买卖记录）
```
id PK, stock_id FK→t_stocks(id) ON DELETE CASCADE,
date TEXT yyyy-MM-dd, price REAL, shares INTEGER,
commission REAL DEFAULT 0, type TEXT('买入'/'卖出'),
expected_range TEXT, expected_buy_low/high REAL, expected_sell_low/high REAL,
note TEXT, created_at TEXT
```

**t_trades**（做T关联：一笔卖出 ←→ 一笔买入的份额）
```
id PK, buy_transaction_id FK→t_transaction_trades(id) ON DELETE CASCADE,
sell_transaction_id FK→t_transaction_trades(id) ON DELETE CASCADE,
shares INTEGER, created_at TEXT
```

### 升级 / 迁移

`_initDatabase` 配置在 `OpenDatabaseOptions`（`version` + `onCreate` + `onUpgrade`）。见 `AGENTS.md`「数据库迁移」法则。当前 `version = 2`：
- `_onCreate`：全新安装建最终 4 张表。
- `_migrateV1ToV2`：把旧库 `accounts/stocks/TransactionTrades/trades` 按字段映射搬到 `t_*`（含 `trades.buy_TransactionTrade_id → t_trades.buy_transaction_id`）。

### 统计口径（改前必读对应方法）

- `getStockFifoSummary(stockId)`：建仓周期成本追踪。`shares` 0→正视为建仓、归零视为清仓；持仓成本 = 周期累计费用 / 持仓股数。
- 返回键含义：`total_shares`(当前持仓) / `total_cost`(累计费用) / `avg_cost`(当前持仓成本) / `cycle_cost`(本周期费用) / `total_avg_cost`(累计成本)。
- `getStockSummary`：简单 `SUM(shares)` 与 `SUM(-price*shares-commission)`。
- `getTTradeProfit`：做T每笔收益，买卖手续费按份额比例分摊。
- 页面展示成本/收益时，务必与这些方法对齐，避免 Login 前后口径不一致。

## 密码工具说明（改前必读对应方法）

- 数据：`insertAccountItem(item)`，新增数据，`updateAccountItem(item)`，更新数据。

## 云端同步

- 服务：坚果云 WebDAV，配置存 `AppConfig`（SharedPreferences）。
- 路径模板：`EverythingTool/{remoteDeviceId}/stock_trading.db`。
- `SyncService`：`upload()` 上传本地库整文件；`download()` 关闭连接→覆盖本地文件→重开。

## 新增一个工具的完整步骤

1. 建模型：`lib/model/{X}Models.dart`。
2. 建页面：`lib/page/{x}/{X}HomePage.dart`。
3. 若需持久化：在 `DatabaseHelper` 增加 CRUD + 统计（改 schema 则走迁移）。
4. 注册：`lib/page/HomePage.dart` 的 `_tools` 加一个 `ToolItem(name, icon, description, pageBuilder)`。
5. **不碰**HomePage 其他逻辑。
6. 跑 `flutter analyze`，无告警、能运行。

## 提交 / 检查清单

- 改动最小化，不顺手重构无关代码。
- 表结构变更必有迁移，`onCreate` 恒为最终结构。
- 新增依赖记得 `flutter pub get`。
- 代码注释用中文，公开 API 可加简短文档注释。