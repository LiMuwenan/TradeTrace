# -*- coding: utf-8 -*-
"""预警列表与已读：默认排除回放、筛选分页、详情快照、已读切换与一键已读。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.storage import meta_db, rule_store
from app.storage.stock_names import StockNameCache

CODE = "sh.600000"
OTHER = "sz.000001"


class FakeProvider:
    def fetch_names(self) -> dict[str, str]:
        return {CODE: "浦发银行", OTHER: "平安银行"}


@pytest.fixture
def client(local_settings) -> TestClient:
    # 名称缓存写一份，避免 names() 走空缓存导致名称断言变空
    StockNameCache(local_settings.meta_dir, FakeProvider()).refresh()
    names = StockNameCache(local_settings.meta_dir, FakeProvider())
    return TestClient(create_app(local_settings, stock_names=names))


def seed(
    local_settings,
    *,
    rule_type="breakout",
    window=60,
    name="突破 60 日",
    threshold=None,
) -> int:
    """建一条规则并返回 id。"""
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        rule = rule_store.create_rule(
            conn, type=rule_type, name=name, window=window, threshold=threshold
        )
        return rule.id
    finally:
        conn.close()


def add_event(
    local_settings,
    *,
    rule_id: int,
    code: str = CODE,
    trade_date: str,
    event: str = "enter",
    replayed: bool = False,
    value: float = 12.3,
    threshold: float | None = None,
    price: float = 12.3,
) -> int:
    """直接写一条变更记录，返回其 id。"""
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        rule_store.record_event(
            conn,
            code=code,
            rule_id=rule_id,
            trade_date=trade_date,
            event=event,
            value=value,
            threshold=threshold,
            price=price,
            replayed=replayed,
        )
        row = rule_store.last_event(conn, code, rule_id)
        return int(row["id"])
    finally:
        conn.close()


def test_list_returns_only_real_alerts_newest_first(client, local_settings):
    rule_id = seed(local_settings)
    add_event(local_settings, rule_id=rule_id, trade_date="2026-06-10")
    add_event(local_settings, rule_id=rule_id, trade_date="2026-06-12")
    # 回放产生的进入不是预警；解除记录也不是
    add_event(local_settings, rule_id=rule_id, trade_date="2025-01-06", replayed=True)
    add_event(local_settings, rule_id=rule_id, trade_date="2026-06-12", event="exit")

    body = client.get("/api/v1/alerts").json()

    assert body["code"] == 0
    items = body["data"]["items"]
    assert [item["tradeDate"] for item in items] == ["2026-06-12", "2026-06-10"]
    assert body["data"]["total"] == 2
    assert body["data"]["unreadCount"] == 2
    assert items[0]["code"] == CODE
    assert items[0]["name"] == "浦发银行"
    assert items[0]["ruleName"] == "突破 60 日"
    assert items[0]["value"] == 12.3
    assert items[0]["readAt"] is None


def test_list_paginates(client, local_settings):
    rule_id = seed(local_settings)
    for day in ("2026-06-09", "2026-06-10", "2026-06-11"):
        add_event(local_settings, rule_id=rule_id, trade_date=day)

    first = client.get("/api/v1/alerts", params={"page": 1, "pageSize": 2}).json()["data"]
    second = client.get("/api/v1/alerts", params={"page": 2, "pageSize": 2}).json()["data"]

    assert [item["tradeDate"] for item in first["items"]] == ["2026-06-11", "2026-06-10"]
    assert [item["tradeDate"] for item in second["items"]] == ["2026-06-09"]
    assert first["total"] == second["total"] == 3


def test_list_filters_by_read_code_and_rule_type(client, local_settings):
    breakout = seed(local_settings, rule_type="breakout", window=60)
    oversold = seed(local_settings, rule_type="oversold", window=60, name="超跌 20%", threshold=20.0)
    read_id = add_event(local_settings, rule_id=breakout, trade_date="2026-06-10")
    add_event(local_settings, rule_id=breakout, code=OTHER, trade_date="2026-06-11")
    add_event(local_settings, rule_id=oversold, trade_date="2026-06-11", threshold=20.0)

    assert client.patch(f"/api/v1/alerts/{read_id}/read", json={"read": True}).status_code == 200

    unread = client.get("/api/v1/alerts", params={"read": "false"}).json()["data"]
    read = client.get("/api/v1/alerts", params={"read": "true"}).json()["data"]
    by_code = client.get("/api/v1/alerts", params={"code": OTHER}).json()["data"]
    by_type = client.get("/api/v1/alerts", params={"ruleType": "oversold"}).json()["data"]

    assert unread["total"] == 2
    assert [item["id"] for item in read["items"]] == [read_id]
    assert by_code["total"] == 1 and by_code["items"][0]["code"] == OTHER
    assert by_type["total"] == 1 and by_type["items"][0]["ruleType"] == "oversold"


def test_detail_returns_snapshot_rule_and_disclaimer(client, local_settings):
    rule_id = seed(local_settings, rule_type="oversold", window=60, name="超跌 20%", threshold=20.0)
    alert_id = add_event(
        local_settings, rule_id=rule_id, trade_date="2026-06-11", value=23.5, threshold=20.0, price=9.8
    )

    body = client.get(f"/api/v1/alerts/{alert_id}").json()

    alert = body["data"]["alert"]
    assert alert["value"] == 23.5
    assert alert["threshold"] == 20.0
    assert alert["price"] == 9.8
    assert alert["tradeDate"] == "2026-06-11"
    rule = body["data"]["rule"]
    assert rule["type"] == "oversold"
    assert rule["window"] == 60
    assert rule["threshold"] == 20.0
    assert "不构成投资建议" in body["data"]["disclaimer"]


def test_detail_of_exit_record_is_404(client, local_settings):
    rule_id = seed(local_settings)
    add_event(local_settings, rule_id=rule_id, trade_date="2026-06-10")
    add_event(local_settings, rule_id=rule_id, trade_date="2026-06-11", event="exit")
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    exit_id = int(rule_store.last_event(conn, CODE, rule_id)["id"])
    conn.close()

    assert client.get(f"/api/v1/alerts/{exit_id}").status_code == 404
    assert client.get("/api/v1/alerts/9999").status_code == 404


def test_toggle_read_both_directions(client, local_settings):
    rule_id = seed(local_settings)
    alert_id = add_event(local_settings, rule_id=rule_id, trade_date="2026-06-10")

    marked = client.patch(f"/api/v1/alerts/{alert_id}/read", json={"read": True}).json()["data"]
    assert marked["read"] is True
    assert marked["readAt"] is not None
    assert marked["unreadCount"] == 0

    unmarked = client.patch(f"/api/v1/alerts/{alert_id}/read", json={"read": False}).json()["data"]
    assert unmarked["read"] is False
    assert unmarked["readAt"] is None
    assert unmarked["unreadCount"] == 1


def test_read_all_only_touches_unread_real_alerts(client, local_settings):
    rule_id = seed(local_settings)
    add_event(local_settings, rule_id=rule_id, trade_date="2026-06-10")
    add_event(local_settings, rule_id=rule_id, trade_date="2026-06-11")
    add_event(local_settings, rule_id=rule_id, trade_date="2025-01-06", replayed=True)

    data = client.post("/api/v1/alerts/read-all").json()["data"]

    assert data["updated"] == 2
    assert data["unreadCount"] == 0
    # 回放记录不参与已读标记，仍是未读形态（也不进列表）
    unread = client.get("/api/v1/alerts", params={"read": "false"}).json()["data"]
    assert unread["total"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"pageSize": 0},
        {"pageSize": 101},
        {"ruleType": "unknown"},
        {"read": "maybe"},
        {"code": "abc"},
    ],
)
def test_invalid_query_is_400(client, params):
    assert client.get("/api/v1/alerts", params=params).status_code == 400


def test_read_toggle_missing_field_is_422(client, local_settings):
    rule_id = seed(local_settings)
    alert_id = add_event(local_settings, rule_id=rule_id, trade_date="2026-06-10")

    response = client.patch(f"/api/v1/alerts/{alert_id}/read", json={})

    assert response.status_code == 422
    assert response.json()["code"] == 422


def test_replayed_record_is_not_an_alert(client, local_settings):
    """静默回放产生的进入记录不是预警：既不能查详情，也不能被标已读。"""
    rule_id = seed(local_settings)
    add_event(local_settings, rule_id=rule_id, trade_date="2025-01-06", replayed=True)
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    replayed_id = int(rule_store.last_event(conn, CODE, rule_id)["id"])
    conn.close()

    assert client.get(f"/api/v1/alerts/{replayed_id}").status_code == 404
    assert client.patch(f"/api/v1/alerts/{replayed_id}/read", json={"read": True}).status_code == 404
