# -*- coding: utf-8 -*-
"""个股详情：日 K 与均线（04 号票）。

三条口径，与 05 的判定保持一致，否则「图上看着穿越了、规则却说没穿越」：
- 图上一律用后复权价（`adjOpen/adjHigh/adjLow/adjClose`），页面必须标注；
- 停牌日既不画进图里，也不参与均线——画成一根平直线会凭空造出一个平台；
- 均线为简单移动平均，窗口按「可交易日」计数，前 `window - 1` 个点没有值。
"""
from __future__ import annotations

from datetime import date, timedelta

from app.config import Settings
from app.storage.parquet_store import ParquetStore
from app.storage.schema import normalize_code
from app.storage.stock_names import StockNameCache
from app.storage.watchlist_store import load_watchlist

# 时间范围：按自然日回溯，再对齐到最近的交易日
RANGE_DAYS = {"3m": 91, "1y": 365, "all": None}
DEFAULT_RANGE = "1y"
MA_WINDOWS = (5, 10, 20, 60)
ADJUST_NOTE = "价格为后复权（原始价 × 后复权因子），避免除权造成的虚假断层"


def stock_detail(
    settings: Settings,
    stock_names: StockNameCache,
    raw_code: str,
    range_key: str = DEFAULT_RANGE,
) -> dict:
    """某标的的日 K 与均线。数据为空抛 LookupError，代码或范围非法抛 ValueError。"""
    if range_key not in RANGE_DAYS:
        raise ValueError(f"未知的时间范围：{range_key}，可选 {'/'.join(RANGE_DAYS)}")
    code = normalize_code(raw_code)

    bars = ParquetStore(settings.parquet_dir).series(code, None, None)
    tradable = [
        bar for bar in bars if int(bar.get("tradestatus", 1)) == 1 and bar.get("adjClose") is not None
    ]
    if not tradable:
        raise LookupError(f"{code} 暂无行情数据")

    # 均线在全量序列上算，再和展示区间一起裁剪，保证边界处的均线是真实值而非从零起算
    moving = {str(window): _moving_average(tradable, window) for window in MA_WINDOWS}
    start = _range_start(tradable, range_key)
    items = [_to_bar(bar) for bar in tradable[start:]]
    latest = tradable[-1]

    return {
        "code": code,
        "name": stock_names.names().get(code, ""),
        "inWatchlist": code in {entry.code for entry in load_watchlist(settings.meta_dir)},
        "range": range_key,
        "rangeDays": RANGE_DAYS[range_key],
        "latest": {
            "date": latest["date"],
            # 主显后复权（与图一致）；rawClose 给对照行情软件用，避免两个页面数字不同被误认为出错
            "close": latest["adjClose"],
            "rawClose": latest["close"],
            "pctChg": latest.get("pctChg"),
            "volume": latest.get("volume"),
        },
        "items": items,
        "ma": {key: values[start:] for key, values in moving.items()},
        "maWindows": list(MA_WINDOWS),
        "adjustNote": ADJUST_NOTE,
    }


def _moving_average(bars: list[dict], window: int) -> list[float | None]:
    """简单移动平均，与 bars 等长；不足窗口的前几个点为 None。"""
    out: list[float | None] = [None] * len(bars)
    total = 0.0
    for index, bar in enumerate(bars):
        total += float(bar["adjClose"])
        if index >= window:
            total -= float(bars[index - window]["adjClose"])
        if index >= window - 1:
            out[index] = round(total / window, 4)
    return out


def _range_start(bars: list[dict], range_key: str) -> int:
    days = RANGE_DAYS[range_key]
    if days is None:
        return 0
    cutoff = (date.fromisoformat(bars[-1]["date"]) - timedelta(days=days)).isoformat()
    for index, bar in enumerate(bars):
        if bar["date"] >= cutoff:
            return index
    return 0


def _to_bar(bar: dict) -> dict:
    return {
        "date": bar["date"],
        "open": bar["adjOpen"],
        "high": bar["adjHigh"],
        "low": bar["adjLow"],
        "close": bar["adjClose"],
        "volume": bar.get("volume"),
        "pctChg": bar.get("pctChg"),
    }
