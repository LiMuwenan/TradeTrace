# -*- coding: utf-8 -*-
"""数据状态：总行数、日期范围、缺失交易日、最近一次导入结果。"""
from __future__ import annotations

import re
from pathlib import Path

from app.config import Settings
from app.storage.parquet_store import ParquetStore
from app.storage.store_state import load_state

_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


def build_status(settings: Settings) -> dict:
    store = ParquetStore(settings.parquet_dir)
    stats = store.stats()
    raw_dates = _archived_daily_dates(settings.raw_dir)
    stored = store.stored_dates()

    # “缺失交易日”= 已归档原始 CSV 但还没进 Parquet 的日期；没有归档目录时为空。
    # 不引入交易日历，避免把春节等休市日误报成缺失。
    missing = sorted(raw_dates - stored)

    return {
        "totalRows": stats["totalRows"],
        "dateRange": stats["dateRange"],
        "years": stats["years"],
        "missingDates": missing,
        "lastImport": load_state(settings.parquet_dir).last_run,
    }


def _archived_daily_dates(raw_dir: Path) -> set[str]:
    daily_dir = raw_dir / "daily"
    if not daily_dir.is_dir():
        return set()
    dates: set[str] = set()
    for path in daily_dir.glob("*.csv"):
        match = _DATE_RE.match(path.stem)
        if match:
            dates.add(match.group(1))
    return dates
