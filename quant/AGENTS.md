# quant/AGENTS.md

本文件只补充 `quant` 项目特有约束。仓库级规则（协议、禁止事项、Git 准则）见根 `AGENTS.md`，冲突时以根为准。

## 定位

A 股量化数据分析与预警平台。**只读行情，不接交易**：不提供下单入口，不输出投资建议。Web 端负责配置与深度分析，Android 端负责随身查看。

## 技术栈

- 后端：Python 3.11+、FastAPI、uvicorn；配置用 TOML + 标准库 `tomllib`
- 前端：Vue 3 + Vite
- 移动端（后续）：Expo/RN
- 查询层：DuckDB 直读 Parquet（不引入独立数据库服务）

## 目录

```
backend/app/api/      路由，统一前缀 /api/v1
backend/app/services/ 业务逻辑（取数、规则求值、通知、日报）
backend/app/storage/  Parquet 读写与分区
backend/tests/        与 app 平行的测试
web/src/api/          接口封装，页面不直接写 fetch
config/               config.example.toml 入库，config.toml 不入库
data/                 不入库：raw/ 原始 CSV 归档，parquet/ 按年分区，meta/ 用户数据与字典缓存
```

## 数据布局

```
data/raw/daily/YYYY-MM-DD.csv     全市场日 K 横截面（18 列，UTF-8 BOM）
data/raw/factors/YYYY-MM-DD.csv   当日除权清单（可为空，只有除权标的）
data/parquet/YYYY.parquet         派生索引：不复权 OHLCV + 每行 back_factor
data/parquet/store_state.json     因子基准与最近一次导入结果
data/meta/watchlist.json          自选清单（用户数据，不可从行情重建）
data/meta/stock_names.json        代码 → 名称缓存（来自数据源证券清单）
```

所有**行情数据**入库都必须经过 `app/storage/ingest.py` 的 `Ingestor`，不得另开行情写路径。
实时抓取到的数据同样先归档成上面两份 CSV，再走同一条导入路径。
`data/meta/` 下的用户数据与字典缓存不属于行情数据，由各自的 store 原子写入。

## 边界

- **禁止 import 或引用 `lianghua/`、`everything/` 的源码与数据文件**；复用通过复制代码或重建数据实现，不跨项目共享。
- 原始 CSV 是事实源，Parquet 是派生索引；**不得修改已归档的原始文件**。
- 落盘只存不复权价与后复权因子，不存前复权数据。

## 命令

```powershell
# 后端（在 quant/backend 下）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m app          # 监听地址与端口取自 config/config.toml
.\.venv\Scripts\python.exe -m app.import_history [历史目录]  # 默认读 config 的 raw_dir
.\.venv\Scripts\python.exe -m app.daily_update [YYYY-MM-DD]  # 每日增量，默认今天

# 前端（在 quant/web 下）
npm install
npm run dev                                # 开发，/api 代理到 127.0.0.1:8000
npm run build
```

## 约定

- 接口响应统一为 `{code, message, data}`，字段名 camelCase，时间为 ISO 8601 带时区
- 配置非法时启动即失败并给出可操作提示，不做静默兜底
- CORS 只允许显式列出的来源，禁止 `*`
