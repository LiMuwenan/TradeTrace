# -*- coding: utf-8 -*-
"""测试用的行情数据构造器：只写最小必要字段，保持 CSV 的 18 列结构。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.storage.schema import DAILY_COLUMNS, FACTOR_COLUMNS

TRADE_DATE = "2026-06-15"


def bar(
    trade_date: str,
    code: str,
    close: float,
    *,
    preclose: float | None = None,
    volume: str | float = 1000,
    tradestatus: int = 1,
    pct_chg: float = 0,
) -> dict:
    return {
        "date": trade_date,
        "code": code,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "preclose": close if preclose is None else preclose,
        "volume": volume,
        "amount": 100_000,
        "adjustflag": 3,
        "turn": 0.1,
        "tradestatus": tradestatus,
        "pctChg": pct_chg,
        "peTTM": 10,
        "pbMRQ": 1,
        "psTTM": 1,
        "pcfNcfTTM": 1,
        "isST": 0,
    }


def write_daily(root: Path, trade_date: str, rows: list[dict]) -> None:
    path = root / "daily" / f"{trade_date}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=DAILY_COLUMNS).to_csv(path, index=False, encoding="utf-8-sig")


def write_factors(root: Path, file_date: str, rows: list[tuple[str, str, float]]) -> None:
    path = root / "factors" / f"{file_date}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    factor_frame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def write_yearly_factors(root: Path, year: str, rows: list[tuple[str, str, float]]) -> None:
    """按年归档的除权清单：`factors/YYYY.csv`。"""
    path = root / "factors" / f"{year}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    factor_frame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def factor_frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "code": code,
                "dividOperateDate": event_date,
                "foreAdjustFactor": 1 / factor,
                "backAdjustFactor": factor,
                "adjustFactor": factor,
            }
            for code, event_date, factor in rows
        ],
        columns=FACTOR_COLUMNS,
    )


def adj_bars(
    prices: list[float],
    *,
    volumes: list[float] | None = None,
    tradestatus: list[int] | None = None,
    start: str = "2026-01-05",
    code: str = "sh.600000",
) -> list[dict]:
    """构造 `ParquetStore.series()` 形状的行序列，因子为 1，故 adjClose == close。"""
    from datetime import date, timedelta

    day = date.fromisoformat(start)
    rows: list[dict] = []
    for index, price in enumerate(prices):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        rows.append(
            {
                "date": day.isoformat(),
                "code": code,
                "close": price,
                "adjClose": price,
                "volume": 1000.0 if volumes is None else volumes[index],
                "tradestatus": 1 if tradestatus is None else tradestatus[index],
            }
        )
        day += timedelta(days=1)
    return rows
