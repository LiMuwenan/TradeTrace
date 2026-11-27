# -*- coding: utf-8 -*-
"""个股详情：日 K 与均线（04 号票）。

价格口径由 `adjust` 决定，默认后复权：

- `back` 后复权（`adjOpen/adjHigh/adjLow/adjClose`）：与 05 的判定口径一致，
  否则「图上看着穿越了、规则却说没穿越」；页面必须标注；
- `raw` 不复权（交易所原始成交价）：与行情软件对得上，除权日会有真实断层，页面必须标注。

两条口径下均线都与所选口径同源——均线滞后价却用另一个口径算，除权处会凭空多出穿越。
其余三条与 05 的判定保持一致：

- 停牌日既不画进图里，也不参与均线——画成一根平直线会凭空造出一个平台；
- 均线为简单移动平均，窗口按「可交易日」计数，前 `window - 1` 个点没有值；
- 均线在全量序列上算完再随展示区间裁剪，边界处才是真实值。
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

# 价格口径：back = 后复权（默认，与规则求值一致），raw = 不复权（交易所原始价）
ADJUST_FIELDS = {
    "back": ("adjOpen", "adjHigh", "adjLow", "adjClose"),
    "raw": ("open", "high", "low", "close"),
}
DEFAULT_ADJUST = "back"
ADJUST_CLOSE_FIELD = {"back": "adjClose", "raw": "close"}
ADJUST_NOTES = {
    "back": "价格为后复权（原始价 × 后复权因子），避免除权造成的虚假断层",
    "raw": "价格为不复权（交易所原始成交价），除权日会出现价格断层；规则求值仍用后复权价",
}


def stock_detail(
    settings: Settings,
    stock_names: StockNameCache,
    raw_code: str,
    range_key: str = DEFAULT_RANGE,
    adjust: str = DEFAULT_ADJUST,
) -> dict:
    """某标的的日 K 与均线。数据为空抛 LookupError，代码/范围/口径非法抛 ValueError。"""
    if range_key not in RANGE_DAYS:
        raise ValueError(f"未知的时间范围：{range_key}，可选 {'/'.join(RANGE_DAYS)}")
    if adjust not in ADJUST_FIELDS:
        raise ValueError(f"未知的价格口径：{adjust}，可选 {'/'.join(ADJUST_FIELDS)}")
    code = normalize_code(raw_code)

    bars = ParquetStore(settings.parquet_dir).series(code, None, None)
    # 不复权收盘价是原始列，后复权价由它乘因子得来：它缺失即两个口径都无价
    tradable = [
        bar for bar in bars if int(bar.get("tradestatus", 1)) == 1 and bar.get("close") is not None
    ]
    if not tradable:
        raise LookupError(f"{code} 暂无行情数据")

    # 均线在全量序列上算，再和展示区间一起裁剪，保证边界处的均线是真实值而非从零起算
    close_field = ADJUST_CLOSE_FIELD[adjust]
    moving = {str(window): _moving_average(tradable, window, close_field) for window in MA_WINDOWS}
    start = _range_start(tradable, range_key)
    items = [_to_bar(bar, adjust) for bar in tradable[start:]]
    latest = tradable[-1]

    return {
        "code": code,
        "name": stock_names.names().get(code, ""),
        "inWatchlist": code in {entry.code for entry in load_watchlist(settings.meta_dir)},
        "range": range_key,
        "rangeDays": RANGE_DAYS[range_key],
        "adjust": adjust,
        "latest": {
            "date": latest["date"],
            # close 跟随所选口径（与图一致）；另两个口径都给出，页面可对照，避免两个页面数字不同被误认为出错
            "close": latest[close_field],
            "rawClose": latest["close"],
            "adjClose": latest["adjClose"],
            "pctChg": latest.get("pctChg"),
            "volume": latest.get("volume"),
        },
        "items": items,
        "ma": {key: values[start:] for key, values in moving.items()},
        "maWindows": list(MA_WINDOWS),
        "adjustNote": ADJUST_NOTES[adjust],
    }


def _moving_average(bars: list[dict], window: int, close_field: str) -> list[float | None]:
    """简单移动平均，与 bars 等长；不足窗口的前几个点为 None。"""
    out: list[float | None] = [None] * len(bars)
    total = 0.0
    for index, bar in enumerate(bars):
        total += float(bar[close_field])
        if index >= window:
            total -= float(bars[index - window][close_field])
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


def _to_bar(bar: dict, adjust: str) -> dict:
    open_field, high_field, low_field, close_field = ADJUST_FIELDS[adjust]
    return {
        "date": bar["date"],
        "open": bar[open_field],
        "high": bar[high_field],
        "low": bar[low_field],
        "close": bar[close_field],
        "volume": bar.get("volume"),
        "pctChg": bar.get("pctChg"),
    }
