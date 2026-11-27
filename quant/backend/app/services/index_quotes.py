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
import threading
import time
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

# baostock 客户端是**进程级全局 socket**：并发登录会互相踢会话，取数也可能互相打断。
# 所以所有指数取数都排队走这一把锁（可重入，供「回补里套单段取数」使用）。
_FETCH_LOCK = threading.RLock()

# 单次区间取数的跨度上限。整段 2006→今天一次拉完，数据源会中途把连接关掉
# （实测取到 2014 年断开）；切成 5 年一段，每段单独成功、单独落盘，失败也能接着补。
CHUNK_YEARS = 5

# 单段失败重试：连接被关掉是暂时性的，隔一会儿重试通常就能过
CHUNK_RETRIES = 2
RETRY_DELAY_SECONDS = 1.5

# 后台回补的运行态：键是「数据目录 + 代码」，避免不同配置的测试互相干扰
_STATE_LOCK = threading.Lock()
_RUNNING: dict[str, dict] = {}


def sync_range(
    settings: Settings,
    raw_code: str,
    start_date: str,
    end_date: str,
    fetcher: IndexFetcher | None = None,
) -> dict:
    """取单只指数在 [start_date, end_date] 的日线并入库，返回本次写入摘要。

    调用方不必自己加锁：这里会排队，保证进程内同一时刻只有一路在跟数据源说话。
    """
    code = normalize_index_code(raw_code)
    with _FETCH_LOCK:
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
    """补齐该指数到今天的全部历史：首次从 2006 年起拉，之后只补最后一条之后的缺口。

    按 `CHUNK_YEARS` 切段，每段独立成功、独立落盘：整段一次拉完会在中途被数据源关掉
    连接（实测取到 2014 年断开），而分段后失败点之前的进度都是真的，下次接着补即可。
    某一段重试仍失败就停下——后面的段依赖同一条连接，继续只会拿到同样的错。
    """
    code = normalize_index_code(raw_code)
    store = IndexStore(settings.index_parquet_dir)
    last = store.last_date(code)
    start = _next_day(last) if last else HISTORY_START
    end = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
    if start > end:
        return {
            "code": code,
            "rows": 0,
            "start": start,
            "end": end,
            "lastDate": last,
            "chunks": 0,
            "errors": [],
            "upToDate": True,
        }

    chunks = _chunks(start, end)
    rows = 0
    errors: list[str] = []
    for chunk_start, chunk_end in chunks:
        try:
            rows += _sync_chunk(settings, code, chunk_start, chunk_end, fetcher)
        except Exception as exc:  # noqa: BLE001 保留已入库的段，把失败点报给上层
            logger.warning("指数 %s 在 %s~%s 取数失败：%s", code, chunk_start, chunk_end, exc)
            errors.append(f"{chunk_start}~{chunk_end}：{exc}")
            break

    return {
        "code": code,
        "rows": rows,
        "start": start,
        "end": end,
        "lastDate": store.last_date(code),
        "chunks": len(chunks),
        "errors": errors,
        "upToDate": False,
    }


def start_backfill(
    settings: Settings, raw_code: str, fetcher: IndexFetcher | None = None
) -> dict:
    """在后台补齐历史，立刻返回状态：加入自选不该等几分钟的数据下载。

    同一只指数同时只跑一个回补任务，重复调用返回同一个运行态。
    """
    code = normalize_index_code(raw_code)
    key = _state_key(settings, code)
    with _STATE_LOCK:
        running = _RUNNING.get(key)
        if running and running["running"]:
            return dict(running)
        state = {
            "code": code,
            "running": True,
            "rows": 0,
            "errors": [],
            "lastDate": None,
            "startedAt": datetime.now(ZoneInfo(settings.timezone)).isoformat(timespec="seconds"),
            "finishedAt": None,
        }
        _RUNNING[key] = state

    threading.Thread(
        target=_run_backfill,
        args=(key, settings, code, fetcher),
        name=f"index-backfill-{code}",
        daemon=True,
    ).start()
    return dict(state)


def backfill_status(settings: Settings, raw_code: str) -> dict | None:
    """该指数最近一次后台回补的状态；没有跑过返回 None。"""
    try:
        code = normalize_index_code(raw_code)
    except IngestError:
        return None
    with _STATE_LOCK:
        state = _RUNNING.get(_state_key(settings, code))
        return None if state is None else dict(state)


def wait_idle(settings: Settings, timeout: float = 10.0) -> bool:
    """等这个数据目录下所有后台回补跑完；超时返回 False。

    测试用它在用例结束时收尾，避免后台线程写文件与临时目录清理撞车；
    停机时也可以先调一次，让正在写的那一段落盘。
    """
    prefix = f"{settings.index_parquet_dir}|"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with _STATE_LOCK:
            running = [
                state for key, state in _RUNNING.items() if key.startswith(prefix) and state["running"]
            ]
        if not running:
            return True
        time.sleep(0.02)
    return False


def _run_backfill(
    key: str, settings: Settings, code: str, fetcher: IndexFetcher | None
) -> None:
    try:
        report = ensure_history(settings, code, fetcher)
    except Exception as exc:  # noqa: BLE001 后台任务不能把异常丢给无人接的线程
        logger.warning("指数 %s 回补失败：%s", code, exc)
        with _STATE_LOCK:
            state = _RUNNING.get(key) or {"code": code}
            _RUNNING[key] = {
                **state,
                "running": False,
                "errors": [str(exc)],
                "finishedAt": datetime.now(ZoneInfo(settings.timezone)).isoformat(
                    timespec="seconds"
                ),
            }
        return

    with _STATE_LOCK:
        _RUNNING[key] = {
            "code": code,
            "running": False,
            "rows": report.get("rows", 0),
            "errors": report.get("errors", []),
            "lastDate": report.get("lastDate"),
            "startedAt": (_RUNNING.get(key) or {}).get("startedAt"),
            "finishedAt": datetime.now(ZoneInfo(settings.timezone)).isoformat(timespec="seconds"),
        }


def _sync_chunk(
    settings: Settings, code: str, start_date: str, end_date: str, fetcher: IndexFetcher | None
) -> int:
    """取一段，失败重试；仍失败则抛出，由调用方决定停在哪。"""
    last_error: Exception | None = None
    for attempt in range(1, CHUNK_RETRIES + 1):
        try:
            return sync_range(settings, code, start_date, end_date, fetcher)["rows"]
        except Exception as exc:  # noqa: BLE001 网络抖动重试一次，业务错误也走同一条路
            last_error = exc
            if attempt < CHUNK_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
    assert last_error is not None
    raise last_error


def _chunks(start: str, end: str) -> list[tuple[str, str]]:
    """把 [start, end] 按自然年切成不超过 `CHUNK_YEARS` 年的段。"""
    chunks: list[tuple[str, str]] = []
    cursor = date.fromisoformat(start)
    limit = date.fromisoformat(end)
    while cursor <= limit:
        chunk_end = min(date(cursor.year + CHUNK_YEARS - 1, 12, 31), limit)
        chunks.append((cursor.isoformat(), chunk_end.isoformat()))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _state_key(settings: Settings, code: str) -> str:
    return f"{settings.index_parquet_dir}|{code}"


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
            # 与回补同一套切段逻辑：首次加入的指数也按 5 年一段拉，避免一次拉 20 年被断连
            for chunk_start, chunk_end in _chunks(start, trade_date):
                rows += _sync_chunk(settings, code, chunk_start, chunk_end, fetcher)
        except Exception as exc:  # noqa: BLE001 指数取数失败只告警，不阻断收盘链
            logger.warning("%s 指数 %s 增量失败：%s", trade_date, code, exc)
            errors.append(f"{code}: {exc}")
            continue
        touched.append(code)

    return {"codes": len(codes), "touched": touched, "rows": rows, "errors": errors}


def _next_day(value: str) -> str:
    return (date.fromisoformat(value) + timedelta(days=1)).isoformat()
