# -*- coding: utf-8 -*-
"""收盘流水线（10）：阶段隔离、非交易日跳过、游标推进、缺口补跑、定时判定。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.factory import create_app
from app.services import pipeline, rule_eval
from app.services.scheduler import DailyScheduler
from app.storage import meta_db, rule_store
from app.storage.ingest import Ingestor
from app.storage.schema import NoMarketDataError
from app.storage.sources import HistoricalCsvSource
from app.storage.watchlist_store import WatchlistEntry, save_watchlist
from factories import adj_bars, bar, write_daily

CODE = "sh.600000"


class EmptySource:
    """数据源返回空：非交易日的判定信号。"""

    name = "empty"

    def load(self, trade_date: str):
        raise NoMarketDataError(f"{trade_date} 没有取到日 K 数据（非交易日或接口失败）")


class BrokenSource:
    name = "broken"

    def load(self, trade_date: str):
        raise RuntimeError("网络断了")


def seed(settings, tmp_path: Path, prices: list[float]) -> list[dict]:
    save_watchlist(
        settings.meta_dir, [WatchlistEntry(CODE, "浦发银行", "2026-01-01T00:00:00+08:00")]
    )
    rows = adj_bars(prices, code=CODE)
    root = tmp_path / "history"
    for row in rows:
        write_daily(root, row["date"], [bar(row["date"], CODE, row["close"])])
    conn = meta_db.connect(settings.meta_dir, settings.timezone)
    try:
        rule_store.create_rule(conn, type="ma_cross", name="均线 2 日", window=2)
    finally:
        conn.close()
    return rows


def csv_source(tmp_path: Path):
    return lambda: HistoricalCsvSource(tmp_path / "history")


def cursor_of(settings) -> str | None:
    conn = meta_db.connect(settings.meta_dir, settings.timezone)
    try:
        row = conn.execute("SELECT last_success_date FROM pipeline_cursor WHERE id = 1").fetchone()
        return None if row is None else row["last_success_date"]
    finally:
        conn.close()


def test_full_run_records_every_stage(local_settings, tmp_path):
    rows = seed(local_settings, tmp_path, [10, 10, 10, 12])

    record = pipeline.run(local_settings, rows[-1]["date"], source_factory=csv_source(tmp_path))

    assert record["status"] == "ok"
    assert [stage["stage"] for stage in record["stages"]] == ["ingest", "evaluate", "report"]
    assert all(stage["status"] == "ok" for stage in record["stages"])
    assert cursor_of(local_settings) == rows[-1]["date"]


def test_ingest_is_skipped_when_data_already_present(local_settings, tmp_path):
    rows = seed(local_settings, tmp_path, [10, 10, 10, 12])
    Ingestor(local_settings).ingest_day(rows[-1]["date"], HistoricalCsvSource(tmp_path / "history"))

    record = pipeline.run(local_settings, rows[-1]["date"], source_factory=csv_source(tmp_path))

    ingest = record["stages"][0]
    assert ingest["status"] == "skipped"
    assert "已入库" in ingest["detail"]


def test_business_day_flow_produces_alert_and_report(local_settings, tmp_path):
    rows = seed(local_settings, tmp_path, [10, 10, 10, 12])
    Ingestor(local_settings).ingest_day(rows[0]["date"], HistoricalCsvSource(tmp_path / "history"))
    Ingestor(local_settings).ingest_day(rows[1]["date"], HistoricalCsvSource(tmp_path / "history"))
    Ingestor(local_settings).ingest_day(rows[2]["date"], HistoricalCsvSource(tmp_path / "history"))

    record = pipeline.run(local_settings, rows[-1]["date"], source_factory=csv_source(tmp_path))

    assert record["status"] == "ok"
    evaluate = record["stages"][1]
    assert "触发 1" in evaluate["detail"]
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        assert conn.execute("SELECT COUNT(*) FROM daily_report").fetchone()[0] == 1
    finally:
        conn.close()


def test_non_trading_day_is_skipped_without_report(local_settings, tmp_path):
    seed(local_settings, tmp_path, [10, 10, 10])

    record = pipeline.run(
        local_settings, "2026-06-30", source_factory=lambda: EmptySource()
    )

    assert record["status"] == "skipped"
    assert record["stages"][0]["status"] == "skipped"
    assert cursor_of(local_settings) is None
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        assert conn.execute("SELECT COUNT(*) FROM daily_report").fetchone()[0] == 0
    finally:
        conn.close()


def test_ingest_failure_stops_before_evaluate(local_settings, tmp_path):
    seed(local_settings, tmp_path, [10, 10, 10])

    record = pipeline.run(
        local_settings, "2026-06-30", source_factory=lambda: BrokenSource()
    )

    assert record["status"] == "failed"
    assert [stage["stage"] for stage in record["stages"]] == ["ingest"]
    assert "网络断了" in record["stages"][0]["error"]
    assert cursor_of(local_settings) is None


def test_evaluate_failure_keeps_ingested_data(local_settings, tmp_path, monkeypatch):
    rows = seed(local_settings, tmp_path, [10, 10, 10, 12])

    def boom(*args, **kwargs):
        raise RuntimeError("求值炸了")

    monkeypatch.setattr(rule_eval, "evaluate_day", boom)

    record = pipeline.run(local_settings, rows[-1]["date"], source_factory=csv_source(tmp_path))

    assert record["status"] == "failed"
    assert record["stages"][0]["status"] == "ok"  # 取数成果保留
    assert record["stages"][1]["status"] == "failed"
    # 数据确实进了库：失败不回滚已完成的阶段
    assert pipeline.ParquetStore(local_settings.parquet_dir).has_date(rows[-1]["date"])


def test_report_failure_does_not_undo_alerts(local_settings, tmp_path, monkeypatch):
    rows = seed(local_settings, tmp_path, [10, 10, 10, 12])
    for row in rows[:-1]:
        Ingestor(local_settings).ingest_day(row["date"], HistoricalCsvSource(tmp_path / "history"))

    from app.services import report as report_service

    monkeypatch.setattr(
        report_service, "generate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("日报炸了"))
    )

    record = pipeline.run(local_settings, rows[-1]["date"], source_factory=csv_source(tmp_path))

    assert record["status"] == "failed"
    assert record["stages"][1]["status"] == "ok"
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        assert conn.execute("SELECT COUNT(*) FROM rule_state_event").fetchone()[0] >= 1
    finally:
        conn.close()


def test_rerun_same_day_is_idempotent(local_settings, tmp_path):
    rows = seed(local_settings, tmp_path, [10, 10, 10, 12])
    for row in rows[:-1]:
        Ingestor(local_settings).ingest_day(row["date"], HistoricalCsvSource(tmp_path / "history"))

    pipeline.run(local_settings, rows[-1]["date"], source_factory=csv_source(tmp_path))
    pipeline.run(local_settings, rows[-1]["date"], source_factory=csv_source(tmp_path))

    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        enters = conn.execute(
            "SELECT COUNT(*) FROM rule_state_event WHERE event = 'enter' AND replayed = 0"
        ).fetchone()[0]
        reports = conn.execute("SELECT COUNT(*) FROM daily_report").fetchone()[0]
    finally:
        conn.close()
    assert enters == 1
    assert reports == 1


def test_catch_up_runs_failed_date(local_settings, tmp_path):
    rows = seed(local_settings, tmp_path, [10, 10, 10])
    pipeline.run(local_settings, rows[0]["date"], source_factory=lambda: BrokenSource())

    results = pipeline.catch_up(local_settings, rows[0]["date"], source_factory=csv_source(tmp_path))

    assert [item["tradeDate"] for item in results] == [rows[0]["date"]]
    assert results[0]["status"] == "ok"


def test_catch_up_skips_weekend_and_covered_dates(local_settings, tmp_path):
    """2026-06-13 是周六：没有游标时不该把周末算成缺口。"""
    seed(local_settings, tmp_path, [10, 10, 10])

    results = pipeline.catch_up(
        local_settings, "2026-06-13", source_factory=lambda: EmptySource()
    )

    assert results == []


def test_catch_up_covers_workdays_after_cursor(local_settings, tmp_path):
    rows = seed(local_settings, tmp_path, [10, 10, 10])
    pipeline.run(local_settings, rows[0]["date"], source_factory=csv_source(tmp_path))

    results = pipeline.catch_up(
        local_settings, rows[2]["date"], source_factory=lambda: EmptySource()
    )

    assert [item["tradeDate"] for item in results] == [rows[1]["date"], rows[2]["date"]]


# --- 定时判定 -------------------------------------------------------------


def scheduler_at(settings, moment: str) -> DailyScheduler:
    fixed = datetime.fromisoformat(moment).replace(tzinfo=ZoneInfo(settings.timezone))
    return DailyScheduler(settings, runner=lambda *a, **k: {"ok": True}, clock=lambda: fixed)


def test_scheduler_fires_after_close_time(local_settings):
    assert scheduler_at(local_settings, "2026-11-26T15:30:00").due() == "2026-11-26"


def test_scheduler_waits_before_close_time(local_settings):
    assert scheduler_at(local_settings, "2026-11-26T14:59:00").due() is None


def test_scheduler_skips_weekend(local_settings):
    # 2026-11-28 是周六
    assert scheduler_at(local_settings, "2026-11-28T16:00:00").due() is None


def test_scheduler_fires_once_per_day(local_settings):
    scheduler = scheduler_at(local_settings, "2026-11-26T15:30:00")

    assert scheduler.tick() is not None
    assert scheduler.tick() is None


# --- 接口 -----------------------------------------------------------------


def make_client(settings) -> TestClient:
    return TestClient(create_app(settings))


def test_run_endpoint_reports_stages(local_settings, tmp_path):
    rows = seed(local_settings, tmp_path, [10, 10, 10])
    pipeline.run(local_settings, rows[0]["date"], source_factory=csv_source(tmp_path))

    data = make_client(local_settings).get("/api/v1/pipeline/runs").json()["data"]

    assert data["total"] == 1
    assert data["items"][0]["status"] == "ok"
    assert len(data["items"][0]["stages"]) == 3


def test_runs_endpoint_returns_cursor(local_settings, tmp_path):
    rows = seed(local_settings, tmp_path, [10, 10, 10])
    pipeline.run(local_settings, rows[0]["date"], source_factory=csv_source(tmp_path))

    data = make_client(local_settings).get("/api/v1/pipeline/runs").json()["data"]

    assert data["cursor"] == rows[0]["date"]


def test_run_endpoint_rejects_bad_date(local_settings):
    response = make_client(local_settings).post("/api/v1/pipeline/run", json={"date": "2026/01/01"})

    assert response.status_code == 400


def test_runs_endpoint_rejects_bad_paging(local_settings):
    client = make_client(local_settings)

    assert client.get("/api/v1/pipeline/runs", params={"page": 0}).status_code == 400
    assert client.get("/api/v1/pipeline/runs", params={"pageSize": 0}).status_code == 400


# --- 配置 -----------------------------------------------------------------


def test_invalid_schedule_time_fails_loudly(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[schedule]
enabled = true
time = "25:00"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="schedule.time"):
        load_settings(path)


def test_schedule_defaults_to_disabled(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[app]\ntimezone = "Asia/Shanghai"\n', encoding="utf-8")

    assert load_settings(path).schedule_enabled is False
