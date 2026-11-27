# -*- coding: utf-8 -*-
"""个股详情接口（04）：后复权价、停牌剔除、均线对齐、范围裁剪。"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.storage.ingest import Ingestor
from app.storage.sources import HistoricalCsvSource
from app.storage.stock_names import StockNameCache
from app.storage.watchlist_store import WatchlistEntry, save_watchlist
from factories import adj_bars, bar, write_daily, write_yearly_factors

CODE = "sh.600000"


class FakeProvider:
    def fetch_names(self) -> dict[str, str]:
        return {CODE: "浦发银行"}


def make_client(settings) -> TestClient:
    cache = StockNameCache(settings.meta_dir, FakeProvider())
    cache.refresh()  # 详情只读缓存，测试里显式落一次，避免依赖网络
    return TestClient(create_app(settings, stock_names=cache))


def ingest_bars(
    settings, tmp_path: Path, rows: list[dict], factor: float = 1.0, event_index: int = -1
) -> None:
    root = tmp_path / "history"
    for row in rows:
        write_daily(
            root,
            row["date"],
            [bar(row["date"], CODE, row["close"], volume=row["volume"], tradestatus=row["tradestatus"])],
        )
    # 因子事件必须落在「有前一日可比」的那天，否则首次除权无法校验，因子会保持原值。
    # factor == 1 时不写：凭空多一个除权事件会让 ingest 按「前收/preclose」反推比例，把价格整体缩放。
    if factor != 1.0:
        event_date = rows[event_index]["date"]
        write_yearly_factors(root, event_date[:4], [(CODE, event_date, factor)])
    for row in rows:
        Ingestor(settings).ingest_day(row["date"], HistoricalCsvSource(root))


def detail(client: TestClient, range_key: str = "all", adjust: str | None = None) -> dict:
    params = {"range": range_key}
    if adjust is not None:
        params["adjust"] = adjust
    response = client.get(f"/api/v1/stocks/{CODE}/detail", params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_bars_and_ma_are_aligned(local_settings, tmp_path):
    rows = adj_bars([10, 11, 12, 13, 14, 15], code=CODE)
    ingest_bars(local_settings, tmp_path, rows)

    data = detail(make_client(local_settings))

    assert len(data["items"]) == 6
    for window in ("5", "10", "20", "60"):
        assert len(data["ma"][window]) == len(data["items"])


def test_ma_is_none_until_enough_bars(local_settings, tmp_path):
    rows = adj_bars([10, 11, 12, 13, 14, 15], code=CODE)
    ingest_bars(local_settings, tmp_path, rows)

    ma5 = detail(make_client(local_settings))["ma"]["5"]

    assert ma5[:4] == [None, None, None, None]
    assert ma5[4] == pytest.approx(12.0)  # (10+11+12+13+14)/5
    assert ma5[5] == pytest.approx(13.0)


def test_suspended_bars_are_removed_from_chart_and_ma(local_settings, tmp_path):
    # 第 3 天停牌且价格异常：若被算进均线会明显拉高，若被画成平线会出现一个平台
    rows = adj_bars([10, 10, 999, 10, 10, 10, 10], tradestatus=[1, 1, 0, 1, 1, 1, 1], code=CODE)
    ingest_bars(local_settings, tmp_path, rows)

    data = detail(make_client(local_settings))

    assert [item["date"] for item in data["items"]] == [
        rows[0]["date"], rows[1]["date"], rows[3]["date"], rows[4]["date"], rows[5]["date"], rows[6]["date"]
    ]
    assert data["ma"]["5"][-1] == pytest.approx(10.0)


def test_prices_are_back_adjusted(local_settings, tmp_path):
    """除权日：官方因子 2.0 + 前收 10 → preclose 5，图上应显示后复权价 10 而非原始价 5。"""
    rows = adj_bars([10, 5], code=CODE)
    ingest_bars(local_settings, tmp_path, rows, factor=2.0)

    data = detail(make_client(local_settings))

    assert data["adjust"] == "back"
    assert data["items"][-1]["close"] == pytest.approx(10.0)
    assert data["latest"]["close"] == pytest.approx(10.0)
    assert data["latest"]["adjClose"] == pytest.approx(10.0)
    assert data["latest"]["rawClose"] == pytest.approx(5.0)  # 原始价另给，供对照行情软件
    assert "后复权" in data["adjustNote"]


def test_raw_view_returns_exchange_prices(local_settings, tmp_path):
    """不复权口径：图与顶部都是交易所原始价，后复权价仍一并返回供对照。"""
    rows = adj_bars([10, 5], code=CODE)
    ingest_bars(local_settings, tmp_path, rows, factor=2.0)

    data = detail(make_client(local_settings), adjust="raw")

    assert data["adjust"] == "raw"
    assert data["items"][-1]["close"] == pytest.approx(5.0)
    assert data["latest"]["close"] == pytest.approx(5.0)
    assert data["latest"]["rawClose"] == pytest.approx(5.0)
    assert data["latest"]["adjClose"] == pytest.approx(10.0)
    assert "不复权" in data["adjustNote"]


def test_ma_follows_price_basis(local_settings, tmp_path):
    """除权落在序列中间：后复权均线连续（10），不复权均线带真实断层（7）。"""
    rows = adj_bars([10, 10, 10, 5, 5, 5], code=CODE)
    ingest_bars(local_settings, tmp_path, rows, factor=2.0, event_index=3)
    client = make_client(local_settings)

    assert detail(client)["ma"]["5"][-1] == pytest.approx(10.0)
    assert detail(client, adjust="raw")["ma"]["5"][-1] == pytest.approx(7.0)


def test_range_trims_older_bars(local_settings, tmp_path):
    rows = adj_bars([10 + index for index in range(150)], code=CODE)
    ingest_bars(local_settings, tmp_path, rows)
    client = make_client(local_settings)

    all_bars = detail(client, "all")
    three_months = detail(client, "3m")

    assert len(all_bars["items"]) == 150
    assert 1 < len(three_months["items"]) < 150
    assert three_months["items"][-1] == all_bars["items"][-1]


def test_range_keeps_ma_history_aligned(local_settings, tmp_path):
    """裁剪后的均线必须是真实值：不能因为区间起点而把 MA60 重新从 None 开始。"""
    rows = adj_bars([10 + index for index in range(150)], code=CODE)
    ingest_bars(local_settings, tmp_path, rows)

    data = detail(make_client(local_settings), "3m")

    assert all(value is not None for value in data["ma"]["60"])


def test_latest_reports_date_and_change(local_settings, tmp_path):
    rows = adj_bars([10, 11, 12], code=CODE)
    ingest_bars(local_settings, tmp_path, rows)

    data = detail(make_client(local_settings))

    assert data["latest"]["date"] == rows[-1]["date"]
    assert data["latest"]["close"] == pytest.approx(12.0)


def test_in_watchlist_flag(local_settings, tmp_path):
    rows = adj_bars([10, 11], code=CODE)
    ingest_bars(local_settings, tmp_path, rows)
    client = make_client(local_settings)

    assert detail(client)["inWatchlist"] is False

    save_watchlist(
        local_settings.meta_dir, [WatchlistEntry(CODE, "浦发银行", "2026-01-01T00:00:00+08:00")]
    )
    assert detail(client)["inWatchlist"] is True


def test_name_comes_from_cache(local_settings, tmp_path):
    rows = adj_bars([10, 11], code=CODE)
    ingest_bars(local_settings, tmp_path, rows)

    assert detail(make_client(local_settings))["name"] == "浦发银行"


def test_unknown_code_is_404(local_settings):
    response = make_client(local_settings).get("/api/v1/stocks/sz.000001/detail")

    assert response.status_code == 404


def test_bad_code_is_400(local_settings):
    response = make_client(local_settings).get("/api/v1/stocks/abc/detail")

    assert response.status_code == 400
    assert response.json()["message"] == "标的代码格式应为 sh.600000 / sz.000001"


def test_bad_range_is_400(local_settings):
    response = make_client(local_settings).get(
        f"/api/v1/stocks/{CODE}/detail", params={"range": "10y"}
    )

    assert response.status_code == 400
    assert "未知的时间范围" in response.json()["message"]


def test_bad_adjust_is_400(local_settings):
    response = make_client(local_settings).get(
        f"/api/v1/stocks/{CODE}/detail", params={"adjust": "forward"}
    )

    assert response.status_code == 400
    assert "未知的价格口径" in response.json()["message"]


def test_search_still_works_after_moving_route(local_settings):
    response = make_client(local_settings).get("/api/v1/stocks/search", params={"q": "浦发"})

    assert response.status_code == 200
    assert response.json()["code"] == 0
