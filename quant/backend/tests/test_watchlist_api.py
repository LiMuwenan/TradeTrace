# -*- coding: utf-8 -*-
"""自选接口：增删、行情摘要、搜索、持久化与停牌口径。"""
from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.storage.ingest import Ingestor
from app.storage.schema import IngestError
from app.storage.sources import HistoricalCsvSource
from app.storage.stock_names import StockNameCache
from app.storage.watchlist_store import WatchlistEntry, load_watchlist, save_watchlist
from factories import TRADE_DATE, bar, write_daily

NAMES = {
    "sh.600000": "浦发银行",
    "sh.600519": "贵州茅台",
    "sz.000001": "平安银行",
}


class FakeProvider:
    def __init__(self, names: dict[str, str] | None = None, error: Exception | None = None) -> None:
        self.names = dict(NAMES if names is None else names)
        self.error = error
        self.calls = 0

    def fetch_names(self) -> dict[str, str]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return dict(self.names)


def make_client(settings, provider: FakeProvider | None = None) -> TestClient:
    stock_names = StockNameCache(settings.meta_dir, provider or FakeProvider())
    return TestClient(create_app(settings, stock_names=stock_names))


def import_bars(settings, tmp_path, rows, trade_date: str = TRADE_DATE) -> None:
    root = tmp_path / "history"
    write_daily(root, trade_date, rows)
    Ingestor(settings).ingest_day(trade_date, HistoricalCsvSource(root))


def test_empty_watchlist_returns_empty_list(local_settings):
    data = make_client(local_settings).get("/api/v1/watchlist").json()["data"]

    assert data == {"items": [], "count": 0}


def test_add_returns_latest_quote_from_source_fields(local_settings, tmp_path):
    import_bars(local_settings, tmp_path, [bar(TRADE_DATE, "sh.600000", 10.5, pct_chg=3.2)])
    client = make_client(local_settings)

    body = client.post("/api/v1/watchlist", json={"code": "600000"}).json()

    assert body["code"] == 0
    data = body["data"]
    assert data["created"] is True
    item = data["item"]
    assert item["code"] == "sh.600000"
    assert item["name"] == "浦发银行"
    assert item["date"] == TRADE_DATE
    assert item["close"] == 10.5
    # 涨跌幅取源字段，而不是用 close/preclose 反算
    assert item["pctChg"] == 3.2
    assert item["suspended"] is False

    listing = client.get("/api/v1/watchlist").json()["data"]
    assert listing["count"] == 1
    assert listing["items"] == [item]


def test_duplicate_add_is_idempotent_and_keeps_order(local_settings, tmp_path):
    import_bars(
        local_settings,
        tmp_path,
        [
            bar(TRADE_DATE, "sh.600000", 10.5),
            bar(TRADE_DATE, "sh.600519", 1500.0),
        ],
    )
    client = make_client(local_settings)
    client.post("/api/v1/watchlist", json={"code": "sh.600000"})
    client.post("/api/v1/watchlist", json={"code": "sh.600519"})

    again = client.post("/api/v1/watchlist", json={"code": "sh.600000"}).json()["data"]

    assert again["created"] is False
    listing = client.get("/api/v1/watchlist").json()["data"]
    assert listing["count"] == 2
    assert [item["code"] for item in listing["items"]] == ["sh.600000", "sh.600519"]


def test_watchlist_survives_restart(local_settings, tmp_path):
    import_bars(local_settings, tmp_path, [bar(TRADE_DATE, "sh.600000", 10.5)])
    make_client(local_settings).post("/api/v1/watchlist", json={"code": "sh.600000"})

    restarted = make_client(local_settings, FakeProvider(error=IngestError("离线")))

    data = restarted.get("/api/v1/watchlist").json()["data"]
    assert data["count"] == 1
    assert data["items"][0]["code"] == "sh.600000"
    assert data["items"][0]["name"] == "浦发银行"


def test_suspended_stock_is_flagged(local_settings, tmp_path):
    import_bars(
        local_settings,
        tmp_path,
        [bar(TRADE_DATE, "sh.600000", 10.0, tradestatus=0, pct_chg=0)],
    )
    client = make_client(local_settings)

    item = client.post("/api/v1/watchlist", json={"code": "sh.600000"}).json()["data"]["item"]

    assert item["suspended"] is True


def test_remove_is_idempotent(local_settings, tmp_path):
    import_bars(local_settings, tmp_path, [bar(TRADE_DATE, "sh.600000", 10.5)])
    client = make_client(local_settings)
    client.post("/api/v1/watchlist", json={"code": "sh.600000"})

    # 输入用不带点的写法，响应里的 code 由 service 归一回传
    first = client.delete("/api/v1/watchlist/sh600000").json()["data"]
    second = client.delete("/api/v1/watchlist/sh.600000").json()["data"]

    assert first == {"code": "sh.600000", "removed": True}
    assert second == {"code": "sh.600000", "removed": False}
    assert client.get("/api/v1/watchlist").json()["data"]["items"] == []


def test_corrupt_watchlist_is_reported_and_not_overwritten(local_settings):
    path = local_settings.meta_dir / "watchlist.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ 不是合法 JSON", encoding="utf-8")
    client = make_client(local_settings)

    listed = client.get("/api/v1/watchlist")
    added = client.post("/api/v1/watchlist", json={"code": "600000"})

    assert listed.status_code == 500
    assert listed.json()["code"] == 500
    assert "自选文件" in listed.json()["message"]
    assert added.status_code == 500
    # 损坏文件必须原样保留，不能被空清单覆盖
    assert path.read_text(encoding="utf-8") == "{ 不是合法 JSON"


def test_legacy_watchlist_json_is_migrated_once(local_settings):
    """旧 watchlist.json 在首次读取时导入 meta.db，原文件改名保留。"""
    legacy = local_settings.meta_dir / "watchlist.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        json.dumps(
            {
                "items": [
                    {"code": "sh.600519", "name": "贵州茅台", "addedAt": "2026-01-01T00:00:00+08:00"},
                    {
                        "code": "sh.000300",
                        "name": "沪深300",
                        "addedAt": "2026-01-02T00:00:00+08:00",
                        "kind": "index",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    client = make_client(local_settings)

    items = client.get("/api/v1/watchlist").json()["data"]["items"]

    # 顺序与旧文件一致，kind 也带过来了（旧条目无 kind 时按股票）
    assert [(item["code"], item["kind"]) for item in items] == [
        ("sh.600519", "stock"),
        ("sh.000300", "index"),
    ]
    assert not legacy.exists()
    assert (local_settings.meta_dir / "watchlist.json.migrated").is_file()


def test_cleared_watchlist_is_not_reimported_from_legacy_file(local_settings):
    """迁移后清空自选必须保持为空——改名旧文件就是为了挡住这条回头路。"""
    legacy = local_settings.meta_dir / "watchlist.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        json.dumps({"items": [{"code": "sh.600000", "name": "浦发银行", "addedAt": ""}]}),
        encoding="utf-8",
    )
    client = make_client(local_settings)
    client.delete("/api/v1/watchlist/sh.600000")

    assert client.get("/api/v1/watchlist").json()["data"]["items"] == []


def test_watchlist_rows_live_in_meta_db(local_settings, tmp_path):
    import_bars(local_settings, tmp_path, [bar(TRADE_DATE, "sh.600000", 10.5)])
    client = make_client(local_settings)

    client.post("/api/v1/watchlist", json={"code": "sh.600000"})

    conn = sqlite3.connect(local_settings.meta_dir / "meta.db")
    try:
        rows = conn.execute("SELECT code, name, kind, sort_order FROM watchlist").fetchall()
    finally:
        conn.close()
    assert rows == [("sh.600000", "浦发银行", "stock", 1)]
    # 不再回写 JSON，自选只有 meta.db 一处
    assert not (local_settings.meta_dir / "watchlist.json").exists()


def test_save_watchlist_replaces_everything(local_settings):
    save_watchlist(
        local_settings.meta_dir,
        [WatchlistEntry("sh.600000", "浦发银行", "2026-01-01T00:00:00+08:00")],
    )
    save_watchlist(
        local_settings.meta_dir,
        [
            WatchlistEntry("sh.600519", "贵州茅台", "2026-01-02T00:00:00+08:00"),
            WatchlistEntry("sh.000300", "沪深300", "2026-01-03T00:00:00+08:00", "index"),
        ],
    )

    entries = load_watchlist(local_settings.meta_dir)

    assert [entry.code for entry in entries] == ["sh.600519", "sh.000300"]
    assert entries[1].kind == "index"


def test_add_rejects_invalid_code_with_unified_error(local_settings):
    response = make_client(local_settings).post("/api/v1/watchlist", json={"code": "60000"})

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == 400
    assert body["message"] == "标的代码格式应为 sh.600000 / sz.000001"
    assert "detail" not in body


def test_search_matches_code_and_name_without_duplicate_refresh(local_settings):
    provider = FakeProvider()
    client = make_client(local_settings, provider)

    by_name = client.get("/api/v1/stocks/search", params={"q": "茅台"}).json()["data"]
    by_code = client.get("/api/v1/stocks/search", params={"q": "600000"}).json()["data"]

    assert [item["code"] for item in by_name["items"]] == ["sh.600519"]
    assert by_name["items"][0]["name"] == "贵州茅台"
    assert [item["code"] for item in by_code["items"]] == ["sh.600000"]
    assert by_name["namesAvailable"] is True
    assert provider.calls == 1  # 第二次搜索命中磁盘缓存，不再拉取


def test_search_accepts_the_same_code_formats_as_add(local_settings):
    client = make_client(local_settings)

    for query in ("sh600000", "600000.SH", "600000"):
        data = client.get("/api/v1/stocks/search", params={"q": query}).json()["data"]
        assert [item["code"] for item in data["items"]] == ["sh.600000"]


def test_search_empty_query_reports_cached_names_without_refresh(local_settings):
    provider = FakeProvider()
    client = make_client(local_settings, provider)

    empty = client.get("/api/v1/stocks/search", params={"q": "   "}).json()["data"]
    assert empty["items"] == []
    assert empty["count"] == 0
    assert empty["namesAvailable"] is False  # 尚未刷新，磁盘上没有缓存
    assert provider.calls == 0  # 空查询不触发联网刷新

    client.get("/api/v1/stocks/search", params={"q": "贵州"})
    refreshed = client.get("/api/v1/stocks/search", params={"q": ""}).json()["data"]
    assert refreshed["namesAvailable"] is True
    assert provider.calls == 1


def test_search_falls_back_to_stored_codes_without_names(local_settings, tmp_path):
    import_bars(local_settings, tmp_path, [bar(TRADE_DATE, "sh.600000", 10.5)])
    client = make_client(local_settings, FakeProvider(error=IngestError("断网")))

    data = client.get("/api/v1/stocks/search", params={"q": "600000"}).json()["data"]

    assert data["namesAvailable"] is False
    assert data["items"] == [{"code": "sh.600000", "name": "", "kind": "stock"}]


def test_search_survives_unexpected_refresh_error(local_settings, tmp_path):
    import_bars(local_settings, tmp_path, [bar(TRADE_DATE, "sh.600000", 10.5)])
    client = make_client(local_settings, FakeProvider(error=RuntimeError("socket 未初始化")))

    data = client.get("/api/v1/stocks/search", params={"q": "600000"}).json()["data"]

    assert data["namesAvailable"] is False
    assert data["items"] == [{"code": "sh.600000", "name": "", "kind": "stock"}]


def test_add_survives_unexpected_refresh_error(local_settings, tmp_path):
    import_bars(local_settings, tmp_path, [bar(TRADE_DATE, "sh.600000", 10.5)])
    client = make_client(local_settings, FakeProvider(error=RuntimeError("socket 未初始化")))

    response = client.post("/api/v1/watchlist", json={"code": "600000"})

    assert response.status_code == 200
    item = response.json()["data"]["item"]
    assert item["code"] == "sh.600000"
    assert item["name"] == ""
    assert item["close"] == 10.5


def test_search_result_can_be_added(local_settings, tmp_path):
    import_bars(local_settings, tmp_path, [bar(TRADE_DATE, "sh.600519", 1500.0)])
    client = make_client(local_settings)

    found = client.get("/api/v1/stocks/search", params={"q": "贵州"}).json()["data"]["items"][0]
    added = client.post("/api/v1/watchlist", json={"code": found["code"]}).json()["data"]

    assert added["created"] is True
    assert added["item"]["name"] == "贵州茅台"
    assert added["item"]["close"] == pytest.approx(1500.0)
