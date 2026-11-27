---
id: 01
title: 指数作为独立标的类型（自选 + 详情）
status: done
blocked_by: []
---

## 要做什么

把主要指数（上证指数、深证成指、创业板指、科创50、沪深300、上证50、中证500、中证1000）按股票那样的方式管理：能搜索、能加入自选、能打开详情页看日 K 与均线。取数只允许「单个指数 + 指定日期区间」，不得拉全市场日 K 文件。

## 验收标准

- [x] 指数日线存独立目录 `data/parquet/index/<code>.parquet`，一只一文件，不与股票年度分区混放
- [x] 取数只走单只接口 `query_history_k_data_plus(code, start, end)`；增量只补最后一条之后的缺口
- [x] 首次添加指数时回补全历史（自 2006 年起），回补失败不撤销这次添加
- [x] 搜索框同时返回股票与指数，指数带「指数」标记；加入自选走同一个入口
- [x] 自选清单一份，条目带 `kind`（`stock` / `index`），旧文件无该字段按股票处理
- [x] 指数详情页展示点位、涨跌幅、日 K、均线；**不显示**后复权/不复权切换，并标注「指数没有除权」
- [x] 指数代码必须带市场前缀；裸 6 位代码给出「请带前缀」提示，不静默当股票
- [x] 收盘流水线加 `indexes` 阶段，只跑自选里的指数，单只失败不阻断求值与日报
- [x] 规则求值只遍历股票自选；指数不能作为单只规则的目标
- [x] 移除自选指数不删已入库行情

## 备注

- 决策与代价见 ADR `0010-index-quotes-storage.md`；这是对「所有行情必经 `Ingestor`」的唯一例外，理由写在 ADR 里。
- 被放弃的方案：复用 19 列 schema（空列 + 编造 `tradestatus`）、指数按年分区、归档原始 CSV、把指数纳入规则与预警。
- 不做：指数复权（无意义）、指数预警（等需求出现再评估）。
- 代码位置：`app/storage/index_catalog.py`、`app/storage/index_store.py`、`app/services/index_quotes.py`、`app/services/stock_detail.py` 的 `index_detail`、`app/services/watchlist.py`、`app/services/pipeline.py` 的 `STAGE_INDEXES`、前端 `StockDetailPage.vue` / `Dashboard.vue`。

**实施记录**（2026-11-27）：

- 指数清单 `data/meta/index_catalog.json`，种子 8 条；文件存在时整份以文件为准（否则用户删掉的指数会复活）。
- 裸代码处理：`000300` 这类「数字命中指数清单、股票字典里又没有这只票」的输入直接 400 要求补前缀；`000001`/`000016` 因为股票字典里确有此票，仍按股票处理。
- `CodeFormatError` 从 `IngestError` 分出：接口层据此把股票格式错统一成一句提示，而把「指数必须带前缀」这类更有用的信息原样透出。
- 流水线阶段顺序变为 `ingest → indexes → evaluate → report`；`test_pipeline.py` 里的位置断言改成按名字取阶段，避免以后插阶段又改一遍。
