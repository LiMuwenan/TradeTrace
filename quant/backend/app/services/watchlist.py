# -*- coding: utf-8 -*-
"""自选：搜索标的、增删清单、组装最新行情摘要。

行情摘要只取数据源已有的字段：收盘价用不复权 `close`，涨跌幅用源里的 `pctChg`，
不用收盘价与昨收自行计算（除权日会算错）。停牌只加标记，不改写数值。
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Settings
from app.storage.parquet_store import ParquetStore
from app.storage.schema import IngestError, normalize_code
from app.storage.stock_names import StockNameCache
from app.storage.watchlist_store import WatchlistEntry, load_watchlist, save_watchlist

MAX_SEARCH_LIMIT = 200


def list_watchlist(settings: Settings, stock_names: StockNameCache) -> list[dict]:
    """按添加顺序返回自选及其最新行情。"""
    entries = load_watchlist(settings.meta_dir)
    quotes = ParquetStore(settings.parquet_dir).latest_bars([entry.code for entry in entries])
    names = stock_names.names()
    return [_to_item(entry, quotes.get(entry.code), names.get(entry.code) or entry.name) for entry in entries]


def add_to_watchlist(
    settings: Settings, stock_names: StockNameCache, raw_code: str
) -> tuple[dict, bool]:
    """加入自选；已存在时只刷新名称，返回 (条目, 是否新建)。"""
    code = normalize_code(raw_code)
    entries = load_watchlist(settings.meta_dir)
    name = stock_names.ensure().get(code, "")

    existing = next((entry for entry in entries if entry.code == code), None)
    if existing is not None:
        if name and name != existing.name:
            existing = WatchlistEntry(code=code, name=name, added_at=existing.added_at)
            entries = [existing if entry.code == code else entry for entry in entries]
            save_watchlist(settings.meta_dir, entries)
        return _with_quote(settings, existing), False

    entry = WatchlistEntry(
        code=code,
        name=name,
        added_at=datetime.now(ZoneInfo(settings.timezone)).isoformat(timespec="seconds"),
    )
    entries.append(entry)
    save_watchlist(settings.meta_dir, entries)
    return _with_quote(settings, entry), True


def remove_from_watchlist(settings: Settings, raw_code: str) -> tuple[str, bool]:
    """移除自选；返回 (归一化代码, 是否真的移除)，本来就不在清单里时视为未移除。"""
    code = normalize_code(raw_code)
    entries = load_watchlist(settings.meta_dir)
    remaining = [entry for entry in entries if entry.code != code]
    if len(remaining) == len(entries):
        return code, False
    save_watchlist(settings.meta_dir, remaining)
    return code, True


def search_stocks(
    settings: Settings, stock_names: StockNameCache, query: str, limit: int = 50
) -> tuple[list[dict], bool]:
    """按代码或名称做子串搜索，返回 (结果, 名称字典是否可用)。

    名称字典不可用时退回「只按代码搜索」已入库的标的，不返回全表占位。
    """
    text = (query or "").strip()
    if not text:
        # 空查询不刷新名称字典，只报告磁盘缓存的真实可用性
        return [], bool(stock_names.names())

    capped = max(1, min(int(limit), MAX_SEARCH_LIMIT))
    names = stock_names.ensure()
    available = bool(names)
    if not names:
        names = {code: "" for code in ParquetStore(settings.parquet_dir).codes()}

    needle = text.lower()
    # 与加入接口保持一致：sh600000 / 600000.SH 这类写法先归一，再按代码精确匹配
    try:
        exact = normalize_code(text)
    except IngestError:
        exact = None
    items = [
        {"code": code, "name": name}
        for code, name in sorted(names.items())
        if code == exact or needle in code.lower() or needle in name.lower()
    ][:capped]
    return items, available


def _with_quote(settings: Settings, entry: WatchlistEntry) -> dict:
    quote = ParquetStore(settings.parquet_dir).latest_bars([entry.code]).get(entry.code)
    return _to_item(entry, quote, entry.name)


def _to_item(entry: WatchlistEntry, quote: dict | None, name: str) -> dict:
    return {
        "code": entry.code,
        "name": name,
        "addedAt": entry.added_at,
        "date": quote["date"] if quote else None,
        "close": quote["close"] if quote else None,
        "pctChg": quote["pctChg"] if quote else None,
        "suspended": bool(quote and quote["suspended"]),
    }
