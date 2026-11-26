# -*- coding: utf-8 -*-
"""收盘流水线（10 号票）：增量取数 → 规则求值（含预警推送）→ 日报。

三条纪律：
- **任一阶段失败不抹掉已完成阶段的成果**：取数成功、求值失败，入库的数据仍然保留；
- **数据源返回为空即非交易日**：记 `skipped` 而不是 `failed`，也不生成空日报；
- **同一天重跑幂等**：已入库跳过取数、事件唯一键挡重复预警、日报已投递不改写。

「通知」不单列一个阶段：求值末尾已在同一请求内同步推送（ADR 0008），
再单开一步会把同一批预警推两遍。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from time import perf_counter
from typing import Callable

from app.config import Settings
from app.services import report as report_service
from app.services import rule_eval
from app.storage.ingest import Ingestor
from app.storage.meta_db import connect
from app.storage.parquet_store import ParquetStore
from app.storage.pipeline_store import (
    add_stage,
    advance_cursor,
    failed_dates,
    finish_run,
    get_cursor,
    get_run,
    list_runs as list_run_rows,
    start_run,
)
from app.storage.schema import NoMarketDataError
from app.storage.sources import BaostockFetcher, MarketDataSource, RealtimeSource

logger = logging.getLogger(__name__)

STAGE_INGEST = "ingest"
STAGE_EVALUATE = "evaluate"
STAGE_REPORT = "report"

MAX_CATCH_UP_DAYS = 10


@dataclass(frozen=True)
class StageResult:
    name: str
    status: str  # ok / skipped / failed
    elapsed_ms: int
    detail: str | None = None
    error: str | None = None


def run(
    settings: Settings,
    trade_date: str,
    *,
    source_factory: Callable[[], MarketDataSource] | None = None,
    notifier=None,
    trigger: str = "manual",
) -> dict:
    """跑一个交易日的完整流水线，返回这次运行的记录（含各阶段结果）。"""
    trade_date = _normalize_date(trade_date)
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        run_id = start_run(conn, trade_date, trigger, timezone=settings.timezone)
    finally:
        conn.close()

    stages: list[StageResult] = []
    store = ParquetStore(settings.parquet_dir)

    # --- 取数 -------------------------------------------------------------
    if store.has_date(trade_date):
        stages.append(StageResult(STAGE_INGEST, "skipped", 0, "该交易日数据已入库，跳过取数"))
    else:
        started = perf_counter()
        try:
            source = (source_factory or (lambda: _default_source(settings)))()
            report = Ingestor(settings).ingest_day(trade_date, source)
        except NoMarketDataError as exc:
            # 数据源返回为空：非交易日，不生成日报、不推进游标，也不算失败
            stages.append(StageResult(STAGE_INGEST, "skipped", _elapsed(started), str(exc)))
            return _finish(settings, run_id, stages, "skipped", str(exc))
        except Exception as exc:
            logger.warning("%s 取数失败：%s", trade_date, exc)
            stages.append(StageResult(STAGE_INGEST, "failed", _elapsed(started), error=str(exc)))
            return _finish(settings, run_id, stages, "failed", str(exc))
        stages.append(
            StageResult(
                STAGE_INGEST, "ok", _elapsed(started), f"写入 {report.rows} 行（覆盖 {report.replaced_rows}）"
            )
        )

    # --- 求值（含预警同步推送）-------------------------------------------
    started = perf_counter()
    try:
        summary = rule_eval.evaluate_day(settings, trade_date, notifier=notifier)
    except Exception as exc:
        logger.warning("%s 求值失败：%s", trade_date, exc)
        stages.append(StageResult(STAGE_EVALUATE, "failed", _elapsed(started), error=str(exc)))
        return _finish(settings, run_id, stages, "failed", str(exc))

    push = summary.get("push") or {}
    stages.append(
        StageResult(
            STAGE_EVALUATE,
            "ok",
            _elapsed(started),
            f"求值 {summary.get('evaluated', 0)} 条，触发 {summary.get('entered', 0)}，"
            f"推送成功 {push.get('succeeded', 0)} / 跳过 {push.get('skipped', 0)}",
        )
    )

    # --- 日报 -------------------------------------------------------------
    started = perf_counter()
    try:
        result = report_service.generate(settings, trade_date, notifier=notifier)
    except Exception as exc:
        logger.warning("%s 日报生成失败：%s", trade_date, exc)
        stages.append(StageResult(STAGE_REPORT, "failed", _elapsed(started), error=str(exc)))
        return _finish(settings, run_id, stages, "failed", str(exc))

    stages.append(
        StageResult(STAGE_REPORT, "ok", _elapsed(started), _report_detail(result))
    )

    conn = connect(settings.meta_dir, settings.timezone)
    try:
        advance_cursor(conn, trade_date, timezone=settings.timezone)
    finally:
        conn.close()

    return _finish(settings, run_id, stages, "ok")


def catch_up(
    settings: Settings,
    until: str,
    *,
    source_factory: Callable[[], MarketDataSource] | None = None,
    notifier=None,
    max_days: int = MAX_CATCH_UP_DAYS,
) -> list[dict]:
    """补跑缺口：游标之后、`until`（含）之前尚未成功的交易日。

    缺口不单独建表——游标之后的工作日，加上运行记录里 status='failed' 的日期，就是全部缺口。
    首次运行（游标为空）不回溯历史，只从 `until` 开始，避免刚部署就发起上百次抓取。
    """
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        cursor = get_cursor(conn)
        failed = failed_dates(conn, since=cursor or until, until=until) if cursor else []
    finally:
        conn.close()

    candidates = sorted({*_business_days(cursor, until), *failed})
    pending = [item for item in candidates if item <= until][:max_days]
    return [
        run(
            settings,
            item,
            source_factory=source_factory,
            notifier=notifier,
            trigger="catchup",
        )
        for item in pending
    ]


def scheduled_run(
    settings: Settings,
    today: str,
    *,
    source_factory: Callable[[], MarketDataSource] | None = None,
    notifier=None,
) -> dict:
    """定时入口：先补昨天的缺口，再跑今天。"""
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    caught = catch_up(
        settings, yesterday, source_factory=source_factory, notifier=notifier
    )
    current = run(
        settings,
        today,
        source_factory=source_factory,
        notifier=notifier,
        trigger="scheduled",
    )
    return {"catchUp": caught, "today": current}


def list_runs(
    settings: Settings, *, page: int = 1, page_size: int = 20, trade_date: str | None = None
) -> dict:
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        items, total = list_run_rows(
            conn, page=page, page_size=page_size, trade_date=trade_date
        )
        cursor = get_cursor(conn)
    finally:
        conn.close()
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "cursor": cursor,
    }


def _finish(
    settings: Settings, run_id: int, stages: list[StageResult], status: str, error: str | None = None
) -> dict:
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        for stage in stages:
            add_stage(
                conn,
                run_id,
                stage=stage.name,
                status=stage.status,
                elapsed_ms=stage.elapsed_ms,
                detail=stage.detail,
                error=stage.error,
            )
        finish_run(conn, run_id, status, error=error, timezone=settings.timezone)
        record = get_run(conn, run_id)
    finally:
        conn.close()
    assert record is not None
    return record


def _business_days(start: str | None, end: str) -> list[str]:
    """(start, end] 之间的工作日。节假日不在此排除——由数据源返回为空来判定。"""
    last = date.fromisoformat(end)
    if start is None:
        # 首次运行只试终点日；终点是周末说明本就不该跑
        return [end] if last.weekday() < 5 else []
    current = date.fromisoformat(start) + timedelta(days=1)
    days: list[str] = []
    while current <= last:
        if current.weekday() < 5:
            days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _report_detail(result: dict) -> str:
    if result.get("kept"):
        return "该日日报已投递，保留原文"
    if result.get("delivered"):
        return f"已投递（{result.get('channel') or '未知通道'}）"
    return f"未投递：{result.get('reason') or '未知原因'}"


def _default_source(settings: Settings) -> MarketDataSource:
    return RealtimeSource(BaostockFetcher(), settings.raw_dir)


def _normalize_date(value: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"交易日格式应为 YYYY-MM-DD：{value!r}") from exc


def _elapsed(started: float) -> int:
    return int((perf_counter() - started) * 1000)
