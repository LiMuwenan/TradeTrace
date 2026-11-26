# -*- coding: utf-8 -*-
"""规则管理接口（06）：列表聚合、新建即回放、改参数收尾、启停。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.storage import meta_db, rule_store
from app.storage.ingest import Ingestor
from app.storage.sources import HistoricalCsvSource
from app.storage.stock_names import StockNameCache
from app.storage.watchlist_store import WatchlistEntry, save_watchlist
from factories import adj_bars, bar, write_daily

CODE = "sh.600000"


class FakeProvider:
    def fetch_names(self) -> dict[str, str]:
        return {CODE: "浦发银行"}


def make_client(settings) -> TestClient:
    return TestClient(create_app(settings, stock_names=StockNameCache(settings.meta_dir, FakeProvider())))


def write_market(tmp_path: Path, prices: list[float]) -> list[dict]:
    """只落 CSV，不决定入库到哪一天。"""
    rows = adj_bars(prices, code=CODE)
    root = tmp_path / "history"
    for row in rows:
        write_daily(root, row["date"], [bar(row["date"], CODE, row["close"])])
    return rows


def ingest(settings, tmp_path: Path, rows: list[dict]) -> None:
    for row in rows:
        Ingestor(settings).ingest_day(row["date"], HistoricalCsvSource(tmp_path / "history"))


def seed_market(settings, tmp_path: Path, prices: list[float]) -> list[dict]:
    """写入行情并挂上自选，供回放与求值使用。"""
    save_watchlist(
        settings.meta_dir, [WatchlistEntry(CODE, "浦发银行", "2026-01-01T00:00:00+08:00")]
    )
    rows = write_market(tmp_path, prices)
    ingest(settings, tmp_path, rows)
    return rows


def prepared_rule(settings, tmp_path: Path, prices: list[float], client: TestClient) -> tuple[dict, dict]:
    """先入库到倒数第二天再建规则，让回放结束时处于未触发，最后一天交给求值触发。

    这是真实节奏：规则是在历史已有之后建的，下一根新 K 线才可能产生当天预警。
    """
    save_watchlist(
        settings.meta_dir, [WatchlistEntry(CODE, "浦发银行", "2026-01-01T00:00:00+08:00")]
    )
    rows = write_market(tmp_path, prices)
    ingest(settings, tmp_path, rows[:-1])
    rule = create(client)
    ingest(settings, tmp_path, rows[-1:])
    client.post("/api/v1/rules/evaluate", json={"date": rows[-1]["date"]})
    return rule, rows[-1]


def rows_of(settings, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = meta_db.connect(settings.meta_dir, settings.timezone)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def create(client: TestClient, **payload) -> dict:
    body = {"type": "ma_cross", "name": "均线 2 日", "window": 2, **payload}
    response = client.post("/api/v1/rules", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_list_is_empty_before_any_rule(local_settings):
    body = make_client(local_settings).get("/api/v1/rules").json()["data"]

    assert body == {"items": [], "total": 0, "enabledCount": 0}


def test_create_replays_history_then_enables(local_settings, tmp_path):
    seed_market(local_settings, tmp_path, [10, 10, 10, 12])
    client = make_client(local_settings)

    data = create(client)

    assert data["enabled"] is True
    assert data["replay"] == {"ruleId": data["id"], "codes": 1, "entered": 1, "exited": 0}
    # 回放产生的进入记录必须标 replayed，否则会被当成当天的真预警推出去
    assert all(int(row["replayed"]) == 1 for row in rows_of(local_settings, "SELECT * FROM rule_state_event"))


def test_create_returns_scope_count_and_label(local_settings):
    save_watchlist(
        local_settings.meta_dir,
        [
            WatchlistEntry(CODE, "浦发银行", "2026-01-01T00:00:00+08:00"),
            WatchlistEntry("sz.000001", "平安银行", "2026-01-01T00:00:00+08:00"),
        ],
    )

    data = create(make_client(local_settings), name="突破 60")

    assert data["scopeCount"] == 2
    assert data["scopeLabel"] == "全部自选"
    assert data["typeLabel"] == "均线穿越"


def test_create_with_single_scope_counts_one(local_settings):
    save_watchlist(
        local_settings.meta_dir, [WatchlistEntry(CODE, "浦发银行", "2026-01-01T00:00:00+08:00")]
    )

    data = create(make_client(local_settings), scope="single", scopeCode="600000")

    assert (data["scope"], data["scopeCode"], data["scopeCount"]) == ("single", CODE, 1)


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"window": 1}, "时间窗不得小于 2"),
        ({"type": "oversold", "threshold": 0}, "超跌阈值应在 (0, 100]"),
        ({"type": "volume_surge", "threshold": 0}, "量比阈值必须大于 0"),
        ({"type": "oversold"}, "必须给出阈值"),
        ({"type": "unknown"}, "未知的规则类型"),
        ({"name": "  "}, "规则名称不能为空"),
    ],
)
def test_create_rejects_invalid_params(local_settings, payload, expected):
    response = make_client(local_settings).post(
        "/api/v1/rules", json={"type": "breakout", "name": "x", "window": 20, **payload}
    )

    assert response.status_code == 400
    assert expected in response.json()["message"]


def test_create_validation_error_does_not_leave_a_rule(local_settings):
    make_client(local_settings).post(
        "/api/v1/rules", json={"type": "breakout", "name": "x", "window": 1}
    )

    assert rows_of(local_settings, "SELECT * FROM alert_rule") == []


def test_update_param_closes_old_state_before_applying(local_settings, tmp_path):
    client = make_client(local_settings)
    rule, last = prepared_rule(local_settings, tmp_path, [10, 10, 10, 12], client)
    assert rows_of(local_settings, "SELECT * FROM rule_state_event WHERE replayed = 0")

    data = client.put(
        f"/api/v1/rules/{rule['id']}", json={"name": "均线 3 日", "window": 3, "threshold": None}
    ).json()["data"]

    assert data["window"] == 3
    assert data["closedCodes"] == [CODE]
    last_event = rows_of(
        local_settings,
        "SELECT * FROM rule_state_event WHERE replayed = 0 ORDER BY id DESC LIMIT 1",
    )[0]
    assert (last_event["event"], last_event["reason"]) == ("exit", "rule_changed")


def test_update_name_only_does_not_touch_state(local_settings, tmp_path):
    client = make_client(local_settings)
    rule, _ = prepared_rule(local_settings, tmp_path, [10, 10, 10, 12], client)
    before = len(rows_of(local_settings, "SELECT * FROM rule_state_event"))

    data = client.put(
        f"/api/v1/rules/{rule['id']}", json={"name": "改个名", "window": rule["window"]}
    ).json()["data"]

    assert data["closedCodes"] == []
    assert len(rows_of(local_settings, "SELECT * FROM rule_state_event")) == before


def test_update_rejects_scope_change(local_settings):
    rule = create(make_client(local_settings))

    response = make_client(local_settings).put(
        f"/api/v1/rules/{rule['id']}",
        json={"name": "x", "window": 2, "scope": "single"},
    )

    assert response.status_code == 400
    assert "标的范围不可修改" in response.json()["message"]


def test_update_unknown_rule_is_404(local_settings):
    response = make_client(local_settings).put(
        "/api/v1/rules/999", json={"name": "x", "window": 2}
    )

    assert response.status_code == 404


def test_disable_closes_state_and_excludes_from_evaluation(local_settings, tmp_path):
    client = make_client(local_settings)
    rule, last = prepared_rule(local_settings, tmp_path, [10, 10, 10, 12], client)

    data = client.post(
        f"/api/v1/rules/{rule['id']}/enabled", json={"enabled": False}
    ).json()["data"]

    assert data["rule"]["enabled"] is False
    assert data["closedCodes"] == [CODE]
    assert rows_of(
        local_settings,
        "SELECT * FROM rule_state_event WHERE reason = 'rule_disabled'",
    )
    # 停用后不再参与求值：同一天重跑不应产生新事件
    before = len(rows_of(local_settings, "SELECT * FROM rule_state_event"))
    client.post("/api/v1/rules/evaluate", json={"date": last["date"]})
    assert len(rows_of(local_settings, "SELECT * FROM rule_state_event")) == before


def test_toggle_is_idempotent(local_settings):
    rule = create(make_client(local_settings))

    data = make_client(local_settings).post(
        f"/api/v1/rules/{rule['id']}/enabled", json={"enabled": True}
    ).json()["data"]

    assert data["changed"] is False
    assert data["replay"] is None


def test_enable_after_disable_replays_gap(local_settings, tmp_path):
    """停用期间漏掉的触发要在重新启用时补进历史，且仍标 replayed。"""
    seed_market(local_settings, tmp_path, [10, 10, 10, 12])
    client = make_client(local_settings)
    rule = create(client)
    client.post(f"/api/v1/rules/{rule['id']}/enabled", json={"enabled": False})

    data = client.post(
        f"/api/v1/rules/{rule['id']}/enabled", json={"enabled": True}
    ).json()["data"]

    assert data["rule"]["enabled"] is True
    assert data["replay"] is not None


def test_list_shows_last_trigger_and_counts(local_settings, tmp_path):
    client = make_client(local_settings)
    rule, last = prepared_rule(local_settings, tmp_path, [10, 10, 10, 12], client)

    data = client.get("/api/v1/rules").json()["data"]

    assert data["total"] == 1
    assert data["enabledCount"] == 1
    assert data["items"][0]["lastTriggeredAt"] == last["date"]
    assert data["items"][0]["id"] == rule["id"]
