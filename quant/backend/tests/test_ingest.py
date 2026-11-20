# -*- coding: utf-8 -*-
"""导入与存储：唯一写入口、因子前向填充、校验、幂等、原子写入。"""
from __future__ import annotations

import pandas as pd
import pytest

from app.config import Settings
from app.storage.ingest import Ingestor
from app.storage.schema import DAILY_COLUMNS, FACTOR_COLUMNS, IngestError
from app.storage.sources import HistoricalCsvSource, RealtimeSource
from app.storage.store_state import load_state
from factories import TRADE_DATE, bar, factor_frame, write_daily, write_factors


def ingest(settings: Settings, root, trade_date: str = TRADE_DATE):
    return Ingestor(settings).ingest_day(trade_date, HistoricalCsvSource(root))


def series(settings: Settings, code: str) -> list[dict]:
    return Ingestor(settings).store.series(code)


def test_ingest_writes_single_year_file_and_normalizes_codes(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 10), bar(TRADE_DATE, "000001.SZ", 12)])

    report = ingest(local_settings, root)

    assert report.rows == 2
    assert (local_settings.parquet_dir / f"{TRADE_DATE[:4]}.parquet").is_file()
    assert series(local_settings, "sh.600000")[0]["close"] == 10
    assert series(local_settings, "sz.000001")[0]["close"] == 12


def test_back_adjusted_price_is_raw_price_times_factor(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, "2026-06-12", [bar("2026-06-12", "sh.600000", 10.0)])
    write_daily(root, "2026-06-15", [bar("2026-06-15", "sh.600000", 9.6, preclose=9.5)])
    write_factors(root, "2026-06-15", [("sh.600000", "2026-06-15", 1.05)])

    Ingestor(local_settings).ingest_day("2026-06-12", HistoricalCsvSource(root))
    ingest(local_settings, root)

    latest = series(local_settings, "sh.600000")[1]
    assert latest["backFactor"] == pytest.approx(10.0 / 9.5)
    assert latest["adjClose"] == pytest.approx(round(9.6 * 10.0 / 9.5, 4))


def test_factor_is_forward_filled_when_no_new_event(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, "2026-06-11", [bar("2026-06-11", "sh.600000", 10.0), bar("2026-06-11", "sz.000001", 20.0)])
    write_daily(root, "2026-06-12", [bar("2026-06-12", "sh.600000", 9.8, preclose=9.5), bar("2026-06-12", "sz.000001", 20.2)])
    write_daily(root, "2026-06-15", [bar("2026-06-15", "sh.600000", 9.7), bar("2026-06-15", "sz.000001", 20.5)])
    write_factors(root, "2026-06-12", [("sh.600000", "2026-06-12", 1.05)])

    Ingestor(local_settings).import_history(HistoricalCsvSource(root))

    rows = series(local_settings, "sh.600000")
    assert rows[1]["backFactor"] == pytest.approx(10.0 / 9.5)
    assert rows[2]["backFactor"] == pytest.approx(10.0 / 9.5)
    assert all(row["backFactor"] == 1.0 for row in series(local_settings, "sz.000001"))


def test_reingesting_same_day_overwrites_instead_of_duplicating(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 10)])
    ingest(local_settings, root)

    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 11)])
    ingest(local_settings, root)

    rows = series(local_settings, "sh.600000")
    assert len(rows) == 1
    assert rows[0]["close"] == 11


def test_rejects_factor_that_goes_backwards(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, "2026-06-11", [bar("2026-06-11", "sh.600000", 10.0)])
    write_daily(root, "2026-06-12", [bar("2026-06-12", "sh.600000", 9.8, preclose=9.5)])
    write_daily(root, "2026-06-15", [bar("2026-06-15", "sh.600000", 9.9, preclose=9.8)])
    write_factors(root, "2026-06-12", [("sh.600000", "2026-06-12", 1.10)])
    write_factors(root, "2026-06-15", [("sh.600000", "2026-06-15", 1.00)])

    Ingestor(local_settings).ingest_days(["2026-06-11", "2026-06-12"], HistoricalCsvSource(root))

    with pytest.raises(IngestError, match="回退"):
        Ingestor(local_settings).ingest_day("2026-06-15", HistoricalCsvSource(root))

    assert [row["date"] for row in series(local_settings, "sh.600000")] == ["2026-06-11", "2026-06-12"]


def test_rejects_single_event_increment_out_of_range(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, "2026-06-12", [bar("2026-06-12", "sh.600000", 10.0)])
    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 1.02, preclose=1.0)])
    write_factors(root, TRADE_DATE, [("sh.600000", TRADE_DATE, 2.0)])

    Ingestor(local_settings).ingest_day("2026-06-12", HistoricalCsvSource(root))

    with pytest.raises(IngestError, match="增量"):
        ingest(local_settings, root)

    assert [row["date"] for row in series(local_settings, "sh.600000")] == ["2026-06-12"]


def test_failed_ingest_leaves_no_temp_file(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, "2026-06-12", [bar("2026-06-12", "sh.600000", 10.0)])
    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 1.02, preclose=1.0)])
    write_factors(root, TRADE_DATE, [("sh.600000", TRADE_DATE, 2.0)])

    Ingestor(local_settings).ingest_day("2026-06-12", HistoricalCsvSource(root))
    with pytest.raises(IngestError):
        ingest(local_settings, root)

    assert not list(local_settings.parquet_dir.glob("*.tmp"))
    assert (local_settings.parquet_dir / "2026.parquet").is_file()


def test_suspended_rows_are_kept_with_null_volume(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(
        root,
        TRADE_DATE,
        [bar(TRADE_DATE, "sh.600000", 10.0, volume="", tradestatus=0)],
    )

    ingest(local_settings, root)

    row = series(local_settings, "sh.600000")[0]
    assert row["tradestatus"] == 0
    assert row["volume"] is None


def test_failed_ingest_does_not_persist_derived_scales(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, "2026-06-11", [bar("2026-06-11", "sh.600000", 10.0)])
    write_daily(root, "2026-06-12", [bar("2026-06-12", "sh.600000", 9.8, preclose=9.5)])
    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 9.9, preclose=9.8)])
    write_factors(root, "2026-06-12", [("sh.600000", "2026-06-12", 1.05)])
    write_factors(root, TRADE_DATE, [("sh.600000", TRADE_DATE, 1.00)])

    with pytest.raises(IngestError, match="回退"):
        Ingestor(local_settings).ingest_days(
            ["2026-06-11", "2026-06-12", TRADE_DATE], HistoricalCsvSource(root)
        )

    state = load_state(local_settings.parquet_dir)
    assert state.scales == {}
    assert state.last_run["status"] == "error"


def test_suspended_ex_dividend_day_keeps_factor_and_warns(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, "2026-06-10", [bar("2026-06-10", "sh.600000", 11.0, preclose=10.0)])
    write_daily(root, "2026-06-11", [bar("2026-06-11", "sh.600000", 11.0, preclose=10.0)])
    write_factors(root, "2026-06-11", [("sh.600000", "2026-06-11", 11.0)])
    Ingestor(local_settings).import_history(HistoricalCsvSource(root))

    # 模拟 store_state 丢失后重建：因子基准从空开始，只剩 Parquet 里的历史因子
    (local_settings.parquet_dir / "store_state.json").unlink()

    # 停牌日除权：昨收 = preclose，无法从 K 线还原增量
    write_daily(
        root,
        "2026-06-12",
        [bar("2026-06-12", "sh.600000", 11.0, preclose=11.0, volume="", tradestatus=0)],
    )
    write_factors(root, "2026-06-12", [("sh.600000", "2026-06-12", 11.55)])

    report = ingest(local_settings, root, "2026-06-12")

    assert [row["backFactor"] for row in series(local_settings, "sh.600000")] == pytest.approx(
        [1.0, 1.1, 1.1]
    )
    assert any("停牌" in warning for warning in report.warnings)


def test_report_carries_replaced_rows_and_elapsed_time(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(
        root,
        TRADE_DATE,
        [bar(TRADE_DATE, "sh.600000", 10.0), bar(TRADE_DATE, "sz.000001", 20.0)],
    )

    first = ingest(local_settings, root)
    second = ingest(local_settings, root)

    assert first.replaced_rows == 0
    assert second.replaced_rows == 2
    assert second.elapsed_ms >= 0
    assert load_state(local_settings.parquet_dir).last_run["replacedRows"] == 2


class FakeFetcher:
    def __init__(self, daily: pd.DataFrame, factors: pd.DataFrame) -> None:
        self.daily = daily
        self.factors = factors

    def fetch_daily(self, trade_date: str) -> pd.DataFrame:
        return self.daily.copy()

    def fetch_factors(self, trade_date: str) -> pd.DataFrame:
        return self.factors.copy()


def test_realtime_source_archives_raw_csv_in_history_layout(local_settings):
    daily = pd.DataFrame([bar(TRADE_DATE, "sh.600000", 10.0)], columns=DAILY_COLUMNS)
    factors = factor_frame([("sh.600000", TRADE_DATE, 1.05)])
    source = RealtimeSource(FakeFetcher(daily, factors), local_settings.raw_dir)

    Ingestor(local_settings).ingest_day(TRADE_DATE, source)

    daily_path = local_settings.raw_dir / "daily" / f"{TRADE_DATE}.csv"
    factor_path = local_settings.raw_dir / "factors" / f"{TRADE_DATE}.csv"
    assert daily_path.is_file() and factor_path.is_file()
    # 归档文件可直接被历史导入读取
    archived = pd.read_csv(daily_path, encoding="utf-8-sig")
    assert list(archived.columns) == DAILY_COLUMNS
    assert series(local_settings, "sh.600000")[0]["close"] == 10


def test_factor_file_without_daily_file_applies_to_next_trading_day(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, "2026-06-10", [bar("2026-06-10", "sh.600000", 10.0)])
    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 9.8, preclose=9.5)])
    # 除权日是 06-12，但那天没有日 K 文件（周末或漏采），事件要落到下一个交易日
    write_factors(root, "2026-06-12", [("sh.600000", "2026-06-12", 1.06)])

    Ingestor(local_settings).import_history(HistoricalCsvSource(root))

    rows = series(local_settings, "sh.600000")
    assert rows[1]["backFactor"] == pytest.approx(10.0 / 9.5)
