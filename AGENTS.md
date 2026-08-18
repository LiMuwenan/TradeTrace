# AGENTS.md — Agent 军规

本文件是 Trae / Claude / Cursor 等 Agent 在本仓库工作时的**最高优先级行为准则**。开始任何任务前先通读。

> 运行时读上下文：本文件会被自动注入到 Agent 上下文中。`CLAUDE.md` 是它的详细版（架构与规范展开）。两者冲突时遵从本文件。

## 一句话项目定位

`EverythingTool`：一个 Flutter **个人工具集合 App**，目前包含「密码管理」和「股票记录」两个独立工具，支持坚果云 WebDAV 云端同步。

## 铁律（违反 = 改坏项目，务必遵守）

1. **App 名称固定为 `EverythingTool`**，不得改动。
2. **新增工具的唯一入口是 HomePage**：新建页面文件 + 在 `lib/page/HomePage.dart` 的 `_tools` 列表注册一个 `ToolItem`（icon + name + description + pageBuilder）。**禁止改动列表之外的既有代码**。
3. **Windows 上必须对 sqflite 做 FFI 初始化**，否则运行时报错。入口已写在 `lib/main.dart`（`main()` 中 `sqfliteFfiInit()` + `databaseFactory = databaseFactoryFfi`），新增逻辑不要绕过。

## 技术栈

- Flutter / Dart（SDK `^3.9.0`），Material 3。
- 状态：无状态管理库，使用 `StatefulWidget` + `setState`。
- 存储：密码用 `SharedPreferences`（JSON）；股票用 SQLite（`sqflite` + Windows FFI）。
- 通讯：`http`（坚果云 WebDAV）。

## 目录速览（改代码前先定位）

```
lib/
  main.dart                      # 入口，FFI 初始化
  model/
    AccountItem.dart             # 密码账号模型
    StockModels.dart             # 股票：Account/Stock/TransactionTrade/TTrade
  page/
    HomePage.dart                # 首页，工具卡片注册表（新增工具改这里）
    AccountListPage.dart         # 密码列表
    SettingsPage.dart            # WebDAV 配置
    stock/
      StockHomePage.dart         # 股票首页（账户维度汇总）
      StockDetailPage.dart       # 个股详情 + 收益汇总
      ProfitSummaryPage.dart     # 多维收益视图
      AccountManagePage.dart     # 账户管理
      StockTransactionDialog.dart# 买卖记录弹窗
      TTradeDialog.dart          # 做T关联弹窗
  utils/
    DatabaseHelper.dart          # SQLite 单例，全部 CRUD + 统计 + 迁移
    SharedPreferencesHelper.dart # 密码存取
    AppConfig.dart               # SharedPreferences 配置（WebDAV/设备ID）
    SyncService.dart             # 上传/下载数据库到坚果云
    WebDavService.dart           # WebDAV 底层
  widgets/
    AccountDialog.dart, AccountListItem.dart
```

## 架构与数据流（必须理解）

- **密码工具**：SQLite 单库 `stock_trading.db`，由 `DatabaseHelper` 单例管理。
  - 表： `t_password_account`
- **股票工具**：SQLite 单库 `stock_trading.db`，由 `DatabaseHelper` 单例管理。
  - 表：`t_accounts` → `t_stocks` → `t_transaction_trades`，以及关联表 `t_trades`（做T）。
  - 完整 schema 见 `CLAUDE.md` 或 `DatabaseHelper._onCreate`。
- **同步**：`SyncService` 把 SQLite 整个文件上传/下载到坚果云路径 `EverythingTool/{remoteId}/stock_trading.db`。

## 数据库迁移（重要！）

任何「改表名 / 改字段 / 加字段」都必须**保留旧数据迁移**，禁止直接改 `CREATE TABLE` 丢弃数据：

1. `DatabaseHelper._initDatabase()` 里升 `version`（当前 `10`），并在 `onUpgrade` 注册新迁移方法。
2. 在 `_onUpgrade` 里按 `oldVersion < N` 链式调用各版本迁移函数。
3. 迁移模式：`检查旧表存在 → CREATE TABLE 新表 → INSERT INTO ... SELECT 搬数据 → DROP 旧表`。
4. `_onCreate` 始终保持**最终表结构**（全新安装用），迁移只服务旧库升级。
5. 迁移函数里加 `sqlite_master` 存在性判断，防止重复或空迁移报错。

## 统计口径约定（股票，容易算错）

- `shares`：**正=买入，负=卖出**。`TransactionTrade.cost = -price*shares - commission`。
- 持仓成本 = 建仓周期累计费用 / 持仓股数（卖出利润会拉低成本），见 `getStockFifoSummary`。
- 收益 = 卖出减买入价差，扣按份额比例摊薄的手续费。
- 页面做改动前，先读 `DatabaseHelper` 里对应统计方法，确认口径再动手。

## 编码规范

- 文件/类名用 `PascalCase`，变量/方法用 `camelCase`。
- 中文 UI 文案、中文注释。模型字段名用英文。
- 页面布局偏好 Material 3（`useMaterial3: true`，`colorSchemeSeed: Colors.blue`）。
- 新工具的数据模型放 `lib/model/{ToolName}Models.dart`，DB 操作统一走 `DatabaseHelper`。

## 常用命令

```bash
flutter pub get                          # 改完 pubspec 后必跑
flutter analyze                          # 改完代码先检查
flutter run -d windows                   # Windows 桌面上运行（FFI 依赖此环境）
flutter test                             # 跑测试
```

## 收尾自检（每次改完都要做）

- [ ] 没触碰「禁改」文件
- [ ] 新增工具在 `HomePage._tools` 正确注册
- [ ] 任何表结构改动都保留了数据迁移
- [ ] `flutter analyze` 无新增告警