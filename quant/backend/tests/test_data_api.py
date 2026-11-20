# -*- coding: utf-8 -*-
"""数据接口：状态页所需的统计、缺失日期与序列查询。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.storage.ingest import Ingestor
from app.storage.sources import HistoricalCsvSource
from factories import TRADE_DATE, bar, write_daily, write_factors


def client(settings) -> TestClient:
    return TestClient(create_app(settings))


def import_day(settings, root, trade_date: str = TRADE_DATE) -> None:
    Ingestor(settings).ingest_day(trade_date, HistoricalCsvSource(root))


def test_empty_store_reports_zero_rows(local_settings):
    body = client(local_settings).get("/api/v1/data/status").json()

    assert body["code"] == 0
    assert body["data"]["totalRows"] == 0
    assert body["data"]["dateRange"] == {"start": None, "end": None}
    assert body["data"]["missingDates"] == []
    assert body["data"]["lastImport"] is None


def test_status_reports_totals_range_and_last_import(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, "2025-02-14", [bar("2025-02-14", "sh.600000", 10.0)])
    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 11.0)])
    import_day(local_settings, root, "2025-02-14")
    import_day(local_settings, root)

    data = client(local_settings).get("/api/v1/data/status").json()["data"]

    assert data["totalRows"] == 2
    assert data["dateRange"] == {"start": "2025-02-14", "end": TRADE_DATE}
    assert [item["year"] for item in data["years"]] == [2025, 2026]
    assert data["lastImport"]["status"] == "ok"
    assert data["lastImport"]["tradeDates"] == [TRADE_DATE]
    assert data["lastImport"]["rows"] == 1
    assert not [key for key in data if "_" in key]


def test_missing_dates_lists_archived_but_not_ingested_days(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 10.0)])
    import_day(local_settings, root)
    # 已归档到 raw/daily 但尚未入库的日期
    write_daily(local_settings.raw_dir, "2026-06-16", [bar("2026-06-16", "sh.600000", 10.2)])

    data = client(local_settings).get("/api/v1/data/status").json()["data"]

    assert data["missingDates"] == ["2026-06-16"]


def test_series_returns_back_adjusted_prices(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, "2026-06-12", [bar("2026-06-12", "sh.600000", 10.0)])
    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 9.6, preclose=9.5)])
    write_factors(root, TRADE_DATE, [("sh.600000", TRADE_DATE, 1.05)])
    import_day(local_settings, root, "2026-06-12")
    import_day(local_settings, root)

    body = client(local_settings).get(
        "/api/v1/data/series", params={"code": "sh.600000", "start": "2026-06-15"}
    ).json()

    assert body["code"] == 0
    data = body["data"]
    assert data["count"] == 1
    row = data["items"][0]
    assert row["date"] == TRADE_DATE
    assert row["backFactor"] == pytest.approx(10.0 / 9.5)
    assert row["adjClose"] == round(9.6 * (10.0 / 9.5), 4)
    assert not [key for key in row if "_" in key]


def test_series_accepts_bare_code_and_normalizes_it(local_settings, tmp_path):
    root = tmp_path / "history"
    write_daily(root, TRADE_DATE, [bar(TRADE_DATE, "sh.600000", 10.0)])
    import_day(local_settings, root)

    body = client(local_settings).get("/api/v1/data/series", params={"code": "600000"}).json()

    assert body["code"] == 0
    assert body["data"]["code"] == "sh.600000"
    assert body["data"]["count"] == 1


def test_series_rejects_invalid_code_with_unified_error(local_settings):
    response = client(local_settings).get("/api/v1/data/series", params={"code": "60000"})

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == 400
    assert body["message"]
    assert "detail" not in body


def test_series_rejects_reversed_range(local_settings):
    response = client(local_settings).get(
        "/api/v1/data/series",
        params={"code": "sh.600000", "start": "2026-06-15", "end": "2026-06-12"},
    )

    assert response.status_code == 400
