# -*- coding: utf-8 -*-
"""自选：搜索标的（股票 + 指数）、增删清单、组装最新行情摘要。

行情摘要只取数据源已有的字段：收盘价用不复权 `close`，涨跌幅用源里的 `pctChg`，
不用收盘价与昨收自行计算（除权日会算错）。停牌只加标记，不改写数值。

指数与股票共用一份自选清单（条目的 `kind` 区分），但行情来自两套存储：
股票读 `parquet/`（按年分区），指数读 `parquet/index/<code>.parquet`。
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Settings
from app.services import index_quotes
from app.storage.index_catalog import load_catalog, upsert_index
from app.storage.index_store import IndexStore
from app.storage.parquet_store import ParquetStore
from app.storage.schema import IngestError, normalize_code, normalize_index_code
from app.storage.sources import IndexFetcher
from app.storage.stock_names import StockNameCache
from app.storage.watchlist_store import (
    KIND_INDEX,
    KIND_STOCK,
    KINDS,
    WatchlistEntry,
    get_entry,
    load_watchlist,
    remove_entry,
    upsert_entry,
)

MAX_SEARCH_LIMIT = 200


def list_watchlist(settings: Settings, stock_names: StockNameCache) -> list[dict]:
    """按添加顺序返回自选及其最新行情。"""
    entries = load_watchlist(settings.meta_dir)
    stock_codes = [entry.code for entry in entries if entry.kind == KIND_STOCK]
    index_codes = [entry.code for entry in entries if entry.kind == KIND_INDEX]
    stock_quotes = ParquetStore(settings.parquet_dir).latest_bars(stock_codes)
    index_quotes_map = IndexStore(settings.index_parquet_dir).latest_bars(index_codes)
    names = stock_names.names()
    catalog = load_catalog(settings.meta_dir)

    items = []
    for entry in entries:
        if entry.kind == KIND_INDEX:
            items.append(
                _to_item(
                    entry,
                    index_quotes_map.get(entry.code),
                    catalog.get(entry.code) or entry.name,
                    index_quotes.backfill_status(settings, entry.code),
                )
            )
        else:
            items.append(
                _to_item(entry, stock_quotes.get(entry.code), names.get(entry.code) or entry.name)
            )
    return items


def add_to_watchlist(
    settings: Settings,
    stock_names: StockNameCache,
    raw_code: str,
    kind: str | None = None,
    fetcher: IndexFetcher | None = None,
) -> tuple[dict, bool]:
    """加入自选；已存在时只刷新名称与类型，返回 (条目, 是否新建)。

    `kind` 为空时按代码自动判断：带市场前缀且命中指数清单的视为指数，其余按股票。
    首次加入指数会顺手回补全历史（单只一次调用）；取数失败不影响入自选，
    失败原因放进条目的 `historyError`，详情页仍可重试。
    """
    resolved = _resolve_kind(settings, stock_names, raw_code, kind)
    if resolved == KIND_INDEX:
        code, catalog = upsert_index(settings.meta_dir, raw_code)
        name = catalog.get(code, "")
    else:
        code = normalize_code(raw_code)
        name = stock_names.ensure().get(code, "")

    existing = get_entry(settings.meta_dir, code)
    if existing is not None:
        refreshed = existing
        if (name and name != existing.name) or existing.kind != resolved:
            refreshed = WatchlistEntry(
                code=code,
                name=name or existing.name,
                added_at=existing.added_at,
                kind=resolved,
            )
            upsert_entry(settings.meta_dir, refreshed)
        return _with_quote(settings, refreshed), False

    entry = WatchlistEntry(
        code=code,
        name=name,
        added_at=datetime.now(ZoneInfo(settings.timezone)).isoformat(timespec="seconds"),
        kind=resolved,
    )
    upsert_entry(settings.meta_dir, entry)

    if resolved == KIND_INDEX:
        # 回补放后台：首次要拉 20 年历史，几十秒的下装不能让「加入自选」这个请求等着
        # （之前就是同步拉，前端看起来「点了没反应」，而且拉到 2014 年被数据源断连）
        state = index_quotes.start_backfill(settings, code, fetcher)
        # 用 start_backfill 返回的那一刻状态回填，而不是再读一次：再读可能刚好碰上
        # 后台已经跑完，响应就变成「没在回补」，前端不会开始轮询
        return _with_quote(settings, entry, status=state), True
    return _with_quote(settings, entry), True


def remove_from_watchlist(settings: Settings, raw_code: str) -> tuple[str, bool]:
    """移除自选；返回 (归一化代码, 是否真的移除)，本来就不在清单里时视为未移除。

    只删清单条目，不删已入库的指数行情：再添加回来是瞬时可见的，而重拉历史要联网。
    """
    candidates = _code_candidates(raw_code)
    for candidate in candidates:
        if remove_entry(settings.meta_dir, candidate):
            return candidate, True
    return candidates[0], False


def search_stocks(
    settings: Settings, stock_names: StockNameCache, query: str, limit: int = 50
) -> tuple[list[dict], bool]:
    """按代码或名称做子串搜索，返回 (结果, 名称字典是否可用)。

    指数清单是本地数据，先于股票返回：它只有个位数，不会挤掉股票结果；
    名称字典不可用时退回「只按代码搜索」已入库的标的，不返回全表占位。
    """
    text = (query or "").strip()
    if not text:
        # 空查询不刷新名称字典，只报告磁盘缓存的真实可用性
        return [], bool(stock_names.names())

    capped = max(1, min(int(limit), MAX_SEARCH_LIMIT))
    needle = text.lower()
    exact_stock, exact_index = _exact_codes(text)

    items = [
        {"code": code, "name": name, "kind": KIND_INDEX}
        for code, name in sorted(load_catalog(settings.meta_dir).items())
        if code == exact_index or needle in code.lower() or needle in name.lower()
    ]

    names = stock_names.ensure()
    available = bool(names)
    if not names:
        names = {code: "" for code in ParquetStore(settings.parquet_dir).codes()}

    items.extend(
        {"code": code, "name": name, "kind": KIND_STOCK}
        for code, name in sorted(names.items())
        if code == exact_stock or needle in code.lower() or needle in name.lower()
    )
    return items[:capped], available


def _resolve_kind(
    settings: Settings, stock_names: StockNameCache, raw_code: str, kind: str | None
) -> str:
    """显式 kind 优先；没给就只认「带前缀且在指数清单里」的代码，其余一律按股票。

    裸代码有一处陷阱：`000300` 既可能被当成 `sz.000300`（不存在的股票），也可能是
    `sh.000300`（沪深300）。这种「数字命中指数清单、股票字典里又没有这只票」的情况直接
    报错要求补前缀，而不是悄悄建一条查不到行情的股票自选。
    """
    requested = (kind or "").strip().lower()
    if requested and requested not in KINDS:
        raise IngestError(f"未知的标的类型：{kind}，可选 {'/'.join(KINDS)}")
    if requested:
        return requested

    try:
        code = normalize_index_code(raw_code)
    except IngestError:
        code = None
    if code is not None:
        return KIND_INDEX if code in load_catalog(settings.meta_dir) else KIND_STOCK

    digits = "".join(character for character in str(raw_code) if character.isdigit())
    ambiguous = [item for item in load_catalog(settings.meta_dir) if item.endswith(f".{digits}")]
    if ambiguous and normalize_code(raw_code) not in stock_names.names():
        raise IngestError(f"{raw_code} 可能是指数 {ambiguous[0]}，请带市场前缀或从搜索结果中选择")
    return KIND_STOCK


def _exact_codes(text: str) -> tuple[str | None, str | None]:
    """把「600000 / sh.600000 / 000001.SH」分别归一到股票与指数两种代码。

    裸代码只当股票：`000001` 在指数与股票里都是合法代码，只能由用户补前缀来区分。
    """
    try:
        stock = normalize_code(text)
    except IngestError:
        stock = None
    try:
        index = normalize_index_code(text)
    except IngestError:
        index = None
    return stock, index


def _code_candidates(raw_code: str) -> list[str]:
    """删除时两种写法都试一遍：自选里可能存着指数，也可能存着股票。"""
    candidates: list[str] = []
    for normalizer in (normalize_index_code, normalize_code):
        try:
            candidates.append(normalizer(raw_code))
        except IngestError:
            continue
    if not candidates:
        raise IngestError(f"无法识别的标的代码：{raw_code!r}")
    return list(dict.fromkeys(candidates))


def _with_quote(
    settings: Settings, entry: WatchlistEntry, status: dict | None = None
) -> dict:
    if entry.kind == KIND_INDEX:
        quote = IndexStore(settings.index_parquet_dir).latest_bars([entry.code]).get(entry.code)
        name = load_catalog(settings.meta_dir).get(entry.code) or entry.name
        # 调用方已经拿到「刚启动回补」的状态时就用它，别再读一次状态
        return _to_item(
            entry, quote, name, status or index_quotes.backfill_status(settings, entry.code)
        )
    quote = ParquetStore(settings.parquet_dir).latest_bars([entry.code]).get(entry.code)
    return _to_item(entry, quote, entry.name)


def _to_item(
    entry: WatchlistEntry, quote: dict | None, name: str, status: dict | None = None
) -> dict:
    item = {
        "code": entry.code,
        "name": name,
        "kind": entry.kind,
        "addedAt": entry.added_at,
        "date": quote["date"] if quote else None,
        "close": quote["close"] if quote else None,
        "pctChg": quote["pctChg"] if quote else None,
        "suspended": bool(quote and quote["suspended"]),
    }
    if entry.kind == KIND_INDEX:
        # 后台回补的进度：没有数据时前端靠这个字段显示「回补中 / 补数据」，而不是空白
        errors = (status or {}).get("errors") or []
        item["historyPending"] = bool((status or {}).get("running"))
        item["historyError"] = errors[0] if errors else None
    return item
