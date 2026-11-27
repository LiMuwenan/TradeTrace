# -*- coding: utf-8 -*-
"""指数行情：按「单只 + 日期区间」取数、校验、落盘。

与股票取数的三点不同（都是数据源决定的，不是设计选择）：

1. **不能拉全市场**：`query_daily_history_k_AStock` 只含 A 股，指数必须逐只调
   `query_history_k_data_plus`，且必须带显式区间——本模块所有入口都按单只指数走；
2. **没有复权**：指数点位数就是原始值，没有因子可乘，也没有「不复权价」这一说；
3. **没有停牌标记**：数据源当天不返回就是没有这一行，不需要 `tradestatus` 过滤。

不额外归档原始 CSV：股票那样做是因为全市场横截面重取一次很贵，而指数是单只一次调用、
随时可重取，Parquet 行与源字段一一对应（没有因子派生），再存一份 CSV 只是增加不一致的
可能。指数文件名与股票目录分开（`parquet/index/<code>.parquet`），见 `IndexStore`。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from app.config import Settings
from app.storage.index_store import IndexStore
from app.storage.schema import INDEX_COLUMNS, IngestError, normalize_index_code
from app.storage.sources import BaostockIndexFetcher, IndexFetcher
from app.storage.watchlist_store import load_watchlist

logger = logging.getLogger(__name__)

# 指数历史起点：baostock 的指数日线自 2006 年起，早于这个日期没有数据
HISTORY_START = "2006-01-01"


def sync_range(
    settings: Settings,
    raw_code: str,
    start_date: str,
    end_date: str,
    fetcher: IndexFetcher | None = None,
) -> dict:
    """取单只指数在 [start_date, end_date] 的日线并入库，返回本次写入摘要。"""
    code = normalize_index_code(raw_code)
    frame = (fetcher or BaostockIndexFetcher()).fetch_index_daily(code, start_date, end_date)
    normalized = normalize_index_frame(frame, code=code, start_date=start_date, end_date=end_date)
    written = IndexStore(settings.index_parquet_dir).merge(code, normalized)
    return {"code": code, "rows": written, "start": start_date, "end": end_date}


def normalize_index_frame(
    frame: pd.DataFrame, *, code: str, start_date: str, end_date: str
) -> pd.DataFrame:
    """校验并规范化指数日线，保证入库的是「这段区间内的有效行」。"""
    if frame is None or frame.empty:
        return pd.DataFrame(columns=INDEX_COLUMNS)

    missing = [column for column in INDEX_COLUMNS if column not in frame.columns]
    if missing:
        raise IngestError(f"指数日线缺少列：{', '.join(missing)}")

    working = frame[INDEX_COLUMNS].copy()
    working["code"] = code
    working["date"] = working["date"].astype(str).str.strip()

    for column in ("open", "high", "low", "close", "preclose", "volume", "amount", "pctChg"):
        working[column] = pd.to_numeric(working[column], errors="coerce")

    # 数据源用空串表示「无此值」：收盘价缺失的行画不出 K 线，均线也不能用
    working = working[working["close"].notna()]
    working = working[(working["date"] >= start_date) & (working["date"] <= end_date)]
    if working.empty:
        return pd.DataFrame(columns=INDEX_COLUMNS)

    return working.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)


def ensure_history(
    settings: Settings, raw_code: str, fetcher: IndexFetcher | None = None
) -> dict:
    """补齐该指数到今天的全部历史：首次从 2006 年起拉，之后只补最后一条之后的缺口。"""
    code = normalize_index_code(raw_code)
    store = IndexStore(settings.index_parquet_dir)
    last = store.last_date(code)
    start = _next_day(last) if last else HISTORY_START
    end = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
    if start > end:
        return {"code": code, "rows": 0, "start": start, "end": end, "upToDate": True}
    return {**sync_range(settings, code, start, end, fetcher), "upToDate": False}


def sync_watchlist(
    settings: Settings, trade_date: str, fetcher: IndexFetcher | None = None
) -> dict:
    """把自选里的指数补到 `trade_date`：逐只取缺口，单只失败不影响其他指数。"""
    codes = [entry.code for entry in load_watchlist(settings.meta_dir) if entry.kind == "index"]
    store = IndexStore(settings.index_parquet_dir)
    rows = 0
    errors: list[str] = []
    touched: list[str] = []

    for code in codes:
        last = store.last_date(code)
        if last is not None and last >= trade_date:
            continue
        start = _next_day(last) if last else HISTORY_START
        try:
            result = sync_range(settings, code, start, trade_date, fetcher)
        except Exception as exc:  # noqa: BLE001 指数取数失败只告警，不阻断收盘链
            logger.warning("%s 指数 %s 增量失败：%s", trade_date, code, exc)
            errors.append(f"{code}: {exc}")
            continue
        rows += result["rows"]
        touched.append(code)

    return {"codes": len(codes), "touched": touched, "rows": rows, "errors": errors}


def _next_day(value: str) -> str:
    return (date.fromisoformat(value) + timedelta(days=1)).isoformat()
