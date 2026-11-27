# -*- coding: utf-8 -*-
"""指数支持：单只按区间取数、独立目录存储、自选与详情、规则范围排除。"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.services import index_quotes
from app.storage.index_catalog import load_catalog
from app.storage.index_store import IndexStore
from app.storage.schema import INDEX_COLUMNS, IngestError
from app.storage.stock_names import StockNameCache
from app.storage.watchlist_store import (
    KIND_INDEX,
    KIND_STOCK,
    WatchlistEntry,
    load_watchlist,
    save_watchlist,
)

CODE = "sh.000300"


class FakeProvider:
    def fetch_names(self) -> dict[str, str]:
        return {"sh.600000": "浦发银行"}


class FakeIndexFetcher:
    """按「单只 + 区间」返回指数日线，记录每次调用的参数供断言。"""

    def __init__(self, closes: list[float] | None = None, error: str | None = None) -> None:
        self.closes = [100.0, 101.0, 102.0] if closes is None else closes
        self.error = error
        self.calls: list[tuple[str, str, str]] = []

    def fetch_index_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        self.calls.append((code, start_date, end_date))
        if self.error:
            raise IngestError(self.error)
        day = date(2026, 1, 5)
        rows = []
        for close in self.closes:
            while day.weekday() >= 5:
                day += timedelta(days=1)
            rows.append(
                {
                    "date": day.isoformat(),
                    "code": code,
                    "open": f"{close:.2f}",
                    "high": f"{close:.2f}",
                    "low": f"{close:.2f}",
                    "close": f"{close:.2f}",
                    "preclose": f"{close:.2f}",
                    "volume": "1000",
                    "amount": "1000000",
                    "pctChg": "0.5",
                }
            )
            day += timedelta(days=1)
        frame = pd.DataFrame(rows, columns=INDEX_COLUMNS)
        return frame[(frame["date"] >= start_date) & (frame["date"] <= end_date)]


def make_client(settings, fetcher: FakeIndexFetcher | None = None) -> TestClient:
    cache = StockNameCache(settings.meta_dir, FakeProvider())
    cache.refresh()
    return TestClient(
        create_app(settings, stock_names=cache, index_fetcher=fetcher or FakeIndexFetcher())
    )


def test_add_index_backfills_history_and_lists_quote(local_settings):
    fetcher = FakeIndexFetcher()
    client = make_client(local_settings, fetcher)

    response = client.post("/api/v1/watchlist", json={"code": CODE})

    assert response.status_code == 200, response.text
    item = response.json()["data"]["item"]
    assert item["kind"] == KIND_INDEX
    assert item["name"] == "沪深300"
    assert item["close"] == pytest.approx(102.0)
    assert item["historyRows"] == 3
    # 只按「这一只 + 一段区间」取，不拉全市场
    assert [call[0] for call in fetcher.calls] == [CODE]

    listed = client.get("/api/v1/watchlist").json()["data"]["items"]
    assert [(entry["code"], entry["kind"]) for entry in listed] == [(CODE, KIND_INDEX)]
    assert listed[0]["close"] == pytest.approx(102.0)


def test_index_detail_is_point_price_without_adjust_basis(local_settings):
    client = make_client(local_settings, FakeIndexFetcher())
    client.post("/api/v1/watchlist", json={"code": CODE})

    data = client.get(f"/api/v1/stocks/{CODE}/detail", params={"range": "all"}).json()["data"]

    assert data["kind"] == "index"
    assert data["adjust"] == "raw"
    assert "指数没有除权" in data["adjustNote"]
    assert len(data["items"]) == 3
    assert data["latest"]["close"] == pytest.approx(102.0)
    # 三个口径字段同值：指数没有复权，前端据此隐藏切换
    assert data["latest"]["adjClose"] == pytest.approx(102.0)
    assert data["latest"]["rawClose"] == pytest.approx(102.0)
    assert len(data["ma"]["5"]) == len(data["items"])


def test_index_detail_without_data_is_404(local_settings):
    client = make_client(local_settings, FakeIndexFetcher([1.0, 2.0]))

    response = client.get("/api/v1/stocks/sh.000852/detail")

    assert response.status_code == 404


def test_bare_index_code_is_rejected_with_prefix_hint(local_settings):
    client = make_client(local_settings, FakeIndexFetcher())

    response = client.post("/api/v1/watchlist", json={"code": "000300"})

    assert response.status_code == 400
    assert "前缀" in response.json()["message"]


def test_explicit_index_kind_extends_catalog(local_settings):
    client = make_client(local_settings, FakeIndexFetcher([10.0, 11.0]))

    response = client.post("/api/v1/watchlist", json={"code": "sz.399005", "kind": "index"})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["item"]["kind"] == KIND_INDEX
    assert "sz.399005" in load_catalog(local_settings.meta_dir)
    # 清单扩展后，详情接口也能按指数口径查到
    detail = client.get("/api/v1/stocks/sz.399005/detail").json()["data"]
    assert detail["kind"] == "index"


def test_index_sync_only_covers_requested_window(local_settings):
    fetcher = FakeIndexFetcher([100.0, 101.0, 102.0])

    index_quotes.sync_range(local_settings, CODE, "2026-01-05", "2026-01-06", fetcher)

    assert fetcher.calls == [(CODE, "2026-01-05", "2026-01-06")]
    store = IndexStore(local_settings.index_parquet_dir)
    assert store.last_date(CODE) == "2026-01-06"
    assert store.series(CODE)[-1]["close"] == pytest.approx(101.0)


def test_ensure_history_continues_from_last_stored_date(local_settings):
    fetcher = FakeIndexFetcher()
    index_quotes.sync_range(local_settings, CODE, "2026-01-05", "2026-01-05", fetcher)

    index_quotes.ensure_history(local_settings, CODE, fetcher)

    code, start, end = fetcher.calls[-1]
    assert code == CODE
    assert start == "2026-01-06"  # 已入库的最后一天之后
    assert end >= start


def test_index_increment_failure_is_reported_not_raised(local_settings):
    save_watchlist(
        local_settings.meta_dir,
        [WatchlistEntry(CODE, "沪深300", "2026-01-01T00:00:00+08:00", KIND_INDEX)],
    )

    report = index_quotes.sync_watchlist(
        local_settings, "2026-01-07", FakeIndexFetcher(error="断网")
    )

    assert report["rows"] == 0
    assert report["touched"] == []
    assert len(report["errors"]) == 1


def test_rule_scope_ignores_index_entries(local_settings):
    save_watchlist(
        local_settings.meta_dir,
        [
            WatchlistEntry("sh.600000", "浦发银行", "2026-01-01T00:00:00+08:00", KIND_STOCK),
            WatchlistEntry(CODE, "沪深300", "2026-01-01T00:00:00+08:00", KIND_INDEX),
        ],
    )
    client = make_client(local_settings)

    created = client.post(
        "/api/v1/rules",
        json={"type": "ma_cross", "name": "自选均线", "scope": "watchlist", "window": 5},
    )

    assert created.status_code == 201, created.text
    # 覆盖标的数只数股票，指数不进规则范围
    assert created.json()["data"]["scopeCount"] == 1


def test_rule_cannot_target_index_directly(local_settings):
    client = make_client(local_settings)

    response = client.post(
        "/api/v1/rules",
        json={
            "type": "ma_cross",
            "name": "指数均线",
            "scope": "single",
            "scopeCode": CODE,
            "window": 5,
        },
    )

    assert response.status_code == 400
    assert "指数" in response.json()["message"]


def test_removing_index_keeps_its_history(local_settings):
    client = make_client(local_settings, FakeIndexFetcher())
    client.post("/api/v1/watchlist", json={"code": CODE})

    response = client.delete(f"/api/v1/watchlist/{CODE}")

    assert response.status_code == 200
    assert response.json()["data"]["removed"] is True
    assert load_watchlist(local_settings.meta_dir) == []
    # 数据保留：重新添加时不必再联网
    assert IndexStore(local_settings.index_parquet_dir).series(CODE) != []
