# -*- coding: utf-8 -*-
"""求值接口：边沿触发落库、同一天重跑幂等、停牌跳过、推送收尾与静默回放。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.services.notify import PushOutcome
from app.storage import meta_db, rule_store
from app.storage.ingest import Ingestor
from app.storage.schema import IngestError
from app.storage.sources import HistoricalCsvSource
from app.storage.stock_names import StockNameCache
from app.storage.watchlist_store import WatchlistEntry, save_watchlist
from factories import adj_bars, bar, write_daily

CODE = "sh.600000"


class FakeProvider:
    def fetch_names(self) -> dict[str, str]:
        return {CODE: "浦发银行"}


class RecordingNotifier:
    configured = True

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.sent: list[dict] = []

    def send(self, alert: dict) -> PushOutcome:
        self.sent.append(alert)
        return PushOutcome(ok=self.ok, channel="fake", error=None if self.ok else "通道故障")


def import_series(settings, tmp_path: Path, prices: list[float], **kwargs) -> list[dict]:
    rows = adj_bars(prices, code=CODE, **kwargs)
    root = tmp_path / "history"
    for row in rows:
        write_daily(
            root,
            row["date"],
            [bar(row["date"], CODE, row["close"], volume=row["volume"], tradestatus=row["tradestatus"])],
        )
    for row in rows:
        Ingestor(settings).ingest_day(row["date"], HistoricalCsvSource(root))
    return rows


def make_client(settings, notifier=None) -> TestClient:
    stock_names = StockNameCache(settings.meta_dir, FakeProvider())
    return TestClient(create_app(settings, stock_names=stock_names, notifier=notifier))


def add_to_watchlist(settings) -> None:
    save_watchlist(settings.meta_dir, [WatchlistEntry(CODE, "浦发银行", "2026-01-01T00:00:00+08:00")])


def create_rule(settings, **kwargs):
    conn = meta_db.connect(settings.meta_dir, settings.timezone)
    try:
        return rule_store.create_rule(conn, **kwargs)
    finally:
        conn.close()


def events(settings) -> list[sqlite3.Row]:
    conn = meta_db.connect(settings.meta_dir, settings.timezone)
    try:
        return conn.execute("SELECT * FROM rule_state_event ORDER BY id").fetchall()
    finally:
        conn.close()


def evaluate(client: TestClient, trade_date: str, code: str | None = None) -> dict:
    payload: dict = {"date": trade_date}
    if code:
        payload["code"] = code
    response = client.post("/api/v1/rules/evaluate", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.fixture
def env(local_settings, tmp_path):
    add_to_watchlist(local_settings)
    rows = import_series(local_settings, tmp_path, [10, 10, 10, 12])
    return local_settings, rows


def test_enter_is_recorded_with_snapshot(env):
    settings, rows = env
    create_rule(settings, type="ma_cross", name="ma2", window=2)
    client = make_client(settings)

    summary = evaluate(client, rows[-1]["date"])

    assert summary["evaluated"] == 1
    assert summary["entered"] == 1
    assert summary["exited"] == 0
    row = events(settings)[0]
    assert (row["event"], row["price"], row["value"]) == ("enter", 12.0, 11.0)


def test_rerun_same_day_does_not_duplicate(env):
    settings, rows = env
    create_rule(settings, type="ma_cross", name="ma2", window=2)
    client = make_client(settings)

    first = evaluate(client, rows[-1]["date"])
    second = evaluate(client, rows[-1]["date"])

    assert (first["entered"], second["entered"]) == (1, 0)
    assert len(events(settings)) == 1


def test_persisting_condition_does_not_repeat_and_falling_back_exits(local_settings, tmp_path):
    add_to_watchlist(local_settings)
    rows = import_series(local_settings, tmp_path, [10, 10, 10, 12, 13, 10])
    create_rule(local_settings, type="ma_cross", name="ma2", window=2)
    client = make_client(local_settings)

    assert evaluate(client, rows[3]["date"])["entered"] == 1
    assert evaluate(client, rows[4]["date"])["entered"] == 0  # 持续满足，不重复
    summary = evaluate(client, rows[5]["date"])  # 跌破均线 → 解除

    assert summary["exited"] == 1
    assert [row["event"] for row in events(local_settings)] == ["enter", "exit"]


def test_suspended_day_is_skipped(local_settings, tmp_path):
    add_to_watchlist(local_settings)
    rows = import_series(local_settings, tmp_path, [10, 10, 10, 12], tradestatus=[1, 1, 1, 0])
    create_rule(local_settings, type="ma_cross", name="ma2", window=2)
    client = make_client(local_settings)

    summary = evaluate(client, rows[-1]["date"])

    assert summary["evaluated"] == 0
    assert summary["entered"] == 0
    assert events(local_settings) == []


def test_debug_code_limits_scope(local_settings, tmp_path):
    add_to_watchlist(local_settings)
    rows = import_series(local_settings, tmp_path, [10, 10, 10, 12])
    create_rule(local_settings, type="ma_cross", name="ma2", window=2)
    client = make_client(local_settings)

    other = evaluate(client, rows[-1]["date"], code="000001")

    assert other["evaluated"] == 0


def test_not_configured_notifier_leaves_alerts_pending(env):
    settings, rows = env
    create_rule(settings, type="ma_cross", name="ma2", window=2)
    client = make_client(settings)

    summary = evaluate(client, rows[-1]["date"])

    assert summary["push"] == {
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 1,
        "reason": "通知通道尚未配置",
    }
    assert events(settings)[0]["pushed_at"] is None


def test_successful_push_is_marked_and_not_repeated(env):
    settings, rows = env
    create_rule(settings, type="ma_cross", name="ma2", window=2)
    notifier = RecordingNotifier()
    client = make_client(settings, notifier=notifier)

    first = evaluate(client, rows[-1]["date"])
    evaluate(client, rows[-1]["date"])

    assert first["push"]["succeeded"] == 1
    assert len(notifier.sent) == 1
    assert events(settings)[0]["push_channel"] == "fake"


def test_failed_push_keeps_alert_pending(env):
    settings, rows = env
    create_rule(settings, type="ma_cross", name="ma2", window=2)
    client = make_client(settings, notifier=RecordingNotifier(ok=False))

    summary = evaluate(client, rows[-1]["date"])

    assert summary["entered"] == 1
    assert summary["push"]["failed"] == 1
    assert events(settings)[0]["pushed_at"] is None


def test_replay_writes_history_flagged_as_replayed(env):
    settings, rows = env
    rule = create_rule(settings, type="ma_cross", name="ma2", window=2)
    client = make_client(settings)

    summary = client.post(f"/api/v1/rules/{rule.id}/replay").json()["data"]

    assert summary["codes"] == 1
    assert summary["entered"] == 1
    replayed = events(settings)
    assert all(row["replayed"] == 1 for row in replayed)
    assert all(row["pushed_at"] is None for row in replayed)


def test_history_shows_enter_and_exit(local_settings, tmp_path):
    add_to_watchlist(local_settings)
    rows = import_series(local_settings, tmp_path, [10, 10, 10, 12, 13, 10])
    rule = create_rule(local_settings, type="ma_cross", name="ma2", window=2)
    client = make_client(local_settings)
    evaluate(client, rows[3]["date"])
    evaluate(client, rows[5]["date"])

    body = client.get(f"/api/v1/rules/{rule.id}/history", params={"code": "600000"}).json()["data"]

    assert [item["event"] for item in body["items"]] == ["enter", "exit"]
    assert [item["tradeDate"] for item in body["items"]] == [rows[3]["date"], rows[5]["date"]]
    assert body["state"] == "exit"
    assert body["code"] == CODE


def test_history_rejects_bad_code(local_settings):
    rule = create_rule(local_settings, type="ma_cross", name="ma2", window=2)
    client = make_client(local_settings)

    response = client.get(f"/api/v1/rules/{rule.id}/history", params={"code": "abc"})

    assert response.status_code == 400


def test_replay_unknown_rule_is_404(local_settings):
    response = make_client(local_settings).post("/api/v1/rules/999/replay")

    assert response.status_code == 404
    assert response.json()["code"] == 404


def test_invalid_date_is_400(local_settings):
    response = make_client(local_settings).post("/api/v1/rules/evaluate", json={"date": "2026/06/11"})

    assert response.status_code == 400


def test_scope_single_rule_only_touches_its_code(local_settings, tmp_path):
    add_to_watchlist(local_settings)
    rows = import_series(local_settings, tmp_path, [10, 10, 10, 12])
    create_rule(
        local_settings, type="ma_cross", name="单只", scope="single", scope_code="sz.000001", window=2
    )
    client = make_client(local_settings)

    summary = evaluate(client, rows[-1]["date"])

    assert summary["evaluated"] == 0  # 指定标的没有当日数据，自选里的票不参与
