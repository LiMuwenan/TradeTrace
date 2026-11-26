# quant/AGENTS.md

本文件只补充 `quant` 项目特有约束。仓库级规则（协议、禁止事项、Git 准则）见根 `AGENTS.md`，冲突时以根为准。

## 定位

A 股量化数据分析与预警平台。**只读行情，不接交易**：不提供下单入口，不输出投资建议。Web 端负责配置与深度分析，Android 端负责随身查看。

## 技术栈

- 后端：Python 3.11+、FastAPI、uvicorn；配置用 TOML + 标准库 `tomllib`
- 前端：Vue 3 + Vite 6；Tailwind CSS 3 + shadcn 风格组件栈（`class-variance-authority`、`clsx`、`tailwind-merge`、`lucide-vue-next`、`reka-ui`）；图表用 `echarts`，只在个股详情页按需加载（路由懒加载，不进首屏包）
- 移动端（后续）：Expo/RN
- 查询层：DuckDB 直读 Parquet（不引入独立数据库服务）；用户记录落 `meta.db`（SQLite，标准库 `sqlite3`），两者职责不同

## Web 页面风格

Web 端为浅色的现代 SaaS 风格。落地页 `LandingPage` 与控制台 `Dashboard` 之外，另有规则、个股详情、日报、预警列表、预警详情、运行记录、通知设置七页；页面切换由 `vue-router` 负责（`web/src/router.js`），路由为 `/`、`/dashboard`、`/rules`、`/stocks/:code`、`/reports`、`/reports/:date`、`/alerts`、`/alerts/:id`、`/pipeline`、`/settings/notification`。新增页面必须沿用以下约定。

> **2026-11-26 变更**：原约定为「由 `App.vue` 的 `view` 状态切换，不引入 vue-router」。改为路由的原因是预警详情必须能刷新保持、能直接开链接，`ref` 切视图做不到这两点（见 `.scratch/quant-p0/07-alert-list.md`）。视觉与结构约定不变，新增页面仍需沿用控制台的左侧分组侧栏 + 顶栏结构（预警三页通过 `web/src/components/AppShell.vue` 复用）。

**落地页**：渐变光晕 hero、小号大写 eyebrow、大字号紧字距标题、主次按钮、右侧展示卡片、三栏特性区；留白充足，不堆砌信息。

**控制台**：左侧可折叠分组侧栏 + 顶栏（搜索框 / ⌘K / 语言 / 头像）+ 主内容卡片网格；卡片细边框、小圆角、弱阴影；解释性内容用折叠面板。

**实现纪律**：

- 设计 token 统一在 `web/src/style.css` 的 `:root` CSS 变量中，`web/tailwind.config.js` 只做语义映射；新增颜色先加 token，不直接写死色值。
- A 股口径的涨跌色固定为 `--up`（红）/ `--down`（绿），**不得**用后端的 `ok/bad` 语义替代，避免涨跌方向反转。
- 基础组件放 `web/src/components/ui/`，新增页面优先复用；样式合并用 `cn()`（`web/src/lib/utils.js`），不手写 class 冲突处理。
- 页面不直接写 `fetch`，接口调用走 `web/src/api/client.js`。
- `web/src/api/client.js` 与后端接口不属于视觉改造范围；换皮时只动组件与样式，不迁移接口逻辑。

风格来源与改造记录见 `.scratch/quant-p0/12-web-ui-style.md`。

## 目录

```
backend/app/api/      路由，统一前缀 /api/v1
backend/app/services/ 业务逻辑（取数、规则求值、通知、日报、流水线、定时器）
backend/app/storage/  Parquet 读写与分区
backend/tests/        与 app 平行的测试
web/src/api/          接口封装，页面不直接写 fetch
web/src/router.js     路由表：/、/dashboard、/rules、/stocks/:code、/reports、/reports/:date、/alerts、/alerts/:id、/pipeline、/settings/notification
web/src/components/ui/ shadcn 风格基础组件（Button / Card 系列 / Input / Badge）
web/src/lib/utils.js  cn()：clsx + tailwind-merge 的 class 合并
web/tailwind.config.js 语义色 token 映射（见「Web 页面风格」）
config/               config.example.toml 入库，config.toml 不入库
data/                 不入库：raw/ 原始 CSV 归档，parquet/ 按年分区，meta/ 用户数据与字典缓存
```

## 数据布局

```
data/raw/daily/YYYY-MM-DD.csv     全市场日 K 横截面（18 列，UTF-8 BOM）
data/raw/factors/YYYY.csv          按年归并的除权清单（历史目录叫 factor/ 也兼容，旧的 YYYY-MM-DD.csv 仍可读）
data/parquet/YYYY.parquet         派生索引：不复权 OHLCV + 每行 back_factor
data/parquet/store_state.json     因子基准与最近一次导入结果
data/meta/watchlist.json          自选清单（用户数据，不可从行情重建）
data/meta/stock_names.json        代码 → 名称缓存（来自数据源证券清单）
data/meta/meta.db                 用户记录库（SQLite，标准库 sqlite3）：alert_rule 规则定义、rule_state_event 触发态变更记录（预警即其中 event='enter' 且 replayed=0 的行）、notification_config 通知配置、notification_log 投递记录、daily_report 日报快照、pipeline_run / pipeline_stage 运行与阶段记录、pipeline_cursor 增量游标
```

`meta.db` 只存用户记录，不存行情；行情仍在 Parquet。它是嵌入式单文件库，不是独立数据库服务。注意与 `lianghua/data/meta.db` 同名但**完全无关**，禁止跨项目读写（见仓库根 `AGENTS.md`）。

所有**行情数据**入库都必须经过 `app/storage/ingest.py` 的 `Ingestor`，不得另开行情写路径。
实时抓取到的数据同样先归档成上面两份 CSV，再走同一条导入路径。
`data/meta/` 下的用户数据与字典缓存不属于行情数据，由各自的 store 原子写入。

## 边界

- **禁止 import 或引用 `lianghua/`、`everything/` 的源码与数据文件**；复用通过复制代码或重建数据实现，不跨项目共享。
- 原始 CSV 是事实源，Parquet 是派生索引；**不得修改已归档的原始文件**。
- 落盘只存不复权价与后复权因子，不存前复权数据。
- **规则定义只有一个写入口：Web 的规则页**（`app/services/rules.py`）。05 号的 TOML 种子导入已随 06 上线删除，不要再加回配置文件写规则的第二条路径。
- **整条收盘链只有一个入口：`app/services/pipeline.py` 的 `run`**。`app.daily_update` 只做增量取数，不要在那里补求值或推送，否则同一天会出现两条推送路径。
- **定时只用进程内 `asyncio`（`app/services/scheduler.py`）**，不引 cron、不加调度框架；流水线是同步代码，到点后经 `asyncio.to_thread` 执行，不阻塞请求。

## 命令

```powershell
# 后端（在 quant/backend 下）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m app          # 监听地址与端口取自 config/config.toml
.\.venv\Scripts\python.exe -m app.import_history [历史目录]  # 默认读 config 的 raw_dir
.\.venv\Scripts\python.exe -m app.daily_update [YYYY-MM-DD]  # 只做增量取数，不做求值与日报

# 收盘流水线（取数 → 求值推送 → 日报）：定时随服务启动，无需单独进程
# config.toml 里 schedule.enabled = true、schedule.time = "18:00"；
# 补跑或重跑走 Web 运行记录页，或 POST /api/v1/pipeline/run

# 前端（在 quant/web 下）
npm install
npm run dev                                # 开发，/api 代理到 127.0.0.1:8000
npm run build
```

## 约定

- 接口响应统一为 `{code, message, data}`，字段名 camelCase，时间为 ISO 8601 带时区
- 配置非法时启动即失败并给出可操作提示，不做静默兜底
- CORS 只允许显式列出的来源，禁止 `*`
- 读 baostock 结果集一律走 `app/storage/baostock_result.py` 的 `collect_rows`，不用 `result.get_data()`：后者翻页时依赖 pandas 已删除的 `DataFrame.append`，只要结果超过一页就抛错（证券名称字典、每日增量取数都会踩到）
- 证券名称字典（`data/meta/stock_names.json`，按日缓存）由 `python -m app` 启动时后台预热：整份清单要翻几页、约一分钟；预热或刷新失败只降级成「按代码搜索」，不阻断自选与搜索
