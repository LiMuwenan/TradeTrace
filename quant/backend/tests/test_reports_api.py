# -*- coding: utf-8 -*-
"""日报接口（09）：无预警也生成、接近阈值口径、已投递不改写、投递失败不影响生成。"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.services import notify
from app.services.notify import PushOutcome
from app.storage import meta_db, rule_store
from app.storage.ingest import Ingestor
from app.storage.sources import HistoricalCsvSource
from app.storage.watchlist_store import WatchlistEntry, save_watchlist
from factories import adj_bars, bar, write_daily

CODE = "sh.600000"


class FakeReportNotifier:
    configured = True

    def __init__(self, ok: bool = True, explode: bool = False) -> None:
        self.ok = ok
        self.explode = explode
        self.reports: list[dict] = []

    def send(self, alert: dict) -> PushOutcome:  # pragma: no cover - 本文件不测预警
        return PushOutcome(ok=True, channel="fake")

    def send_report(self, report: dict) -> PushOutcome:
        if self.explode:
            raise TimeoutError("通道挂了")
        self.reports.append(report)
        return PushOutcome(ok=self.ok, channel="fake", error=None if self.ok else "发送失败")


class SilentNotifier:
    configured = False


def make_client(settings, notifier=None) -> TestClient:
    return TestClient(create_app(settings, notifier=notifier))


def seed(
    settings,
    tmp_path: Path,
    prices: list[float],
    *,
    rule_type="ma_cross",
    window=2,
    pct_chg_last: float = 0,
) -> tuple[list[dict], int]:
    save_watchlist(
        settings.meta_dir, [WatchlistEntry(CODE, "浦发银行", "2026-01-01T00:00:00+08:00")]
    )
    rows = adj_bars(prices, code=CODE)
    root = tmp_path / "history"
    for index, row in enumerate(rows):
        change = pct_chg_last if index == len(rows) - 1 else 0
        write_daily(root, row["date"], [bar(row["date"], CODE, row["close"], pct_chg=change)])
    for row in rows:
        Ingestor(settings).ingest_day(row["date"], HistoricalCsvSource(root))

    conn = meta_db.connect(settings.meta_dir, settings.timezone)
    try:
        rule = rule_store.create_rule(conn, type=rule_type, name="均线 2 日", window=window)
        return rows, rule.id
    finally:
        conn.close()


def add_trigger(settings, rule_id: int, trade_date: str) -> None:
    conn = meta_db.connect(settings.meta_dir, settings.timezone)
    try:
        rule_store.record_event(
            conn,
            code=CODE,
            rule_id=rule_id,
            trade_date=trade_date,
            event="enter",
            value=9.9,
            price=10.0,
        )
    finally:
        conn.close()


def generate(client: TestClient, trade_date: str) -> dict:
    response = client.post("/api/v1/reports/generate", json={"date": trade_date})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_report_is_generated_even_without_triggers(local_settings, tmp_path):
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10, 10])

    data = generate(make_client(local_settings), rows[-1]["date"])

    assert data["report"]["triggers"] == []
    assert data["report"]["watchlistSummary"]["total"] == 1
    assert data["report"]["dataDate"] == rows[-1]["date"]


def test_report_lists_triggers_and_near_misses(local_settings, tmp_path):
    # 9.8 低于 2 日均线 9.9：未触发，但差距 1% 在 20% 以内 → 应进「接近阈值」
    rows, rule_id = seed(local_settings, tmp_path, [10, 10, 10, 9.8])
    add_trigger(local_settings, rule_id, rows[-1]["date"])

    data = generate(make_client(local_settings), rows[-1]["date"])

    report = data["report"]
    assert len(report["triggers"]) == 1
    assert report["triggers"][0]["code"] == CODE
    assert report["triggers"][0]["ruleName"] == "均线 2 日"
    assert len(report["nearMisses"]) == 1
    assert report["nearMisses"][0]["ruleName"] == "均线 2 日"


def test_far_from_threshold_is_not_near_miss(local_settings, tmp_path):
    # 5.0 对 2 日均线 10.0：差距 50%，不应算接近
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10, 5])

    data = generate(make_client(local_settings), rows[-1]["date"])

    assert data["report"]["nearMisses"] == []


@pytest.mark.parametrize(
    "change, expected",
    [(2.5, "up"), (-1.2, "down"), (0, "flat")],
)
def test_watchlist_summary_counts_direction(local_settings, tmp_path, change, expected):
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10.5], pct_chg_last=change)

    summary = generate(make_client(local_settings), rows[-1]["date"])["report"]["watchlistSummary"]

    assert summary["total"] == 1
    assert summary[expected] == 1
    assert summary["up"] + summary["down"] + summary["flat"] == 1


def test_missing_bar_counts_as_suspended(local_settings, tmp_path):
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10])
    # 求值日没有数据：应记「无当日数据」，不能算平盘
    data = generate(make_client(local_settings), "2026-06-30")

    assert data["report"]["watchlistSummary"]["suspended"] == 1


def test_delivered_report_is_kept_on_rerun(local_settings, tmp_path):
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10, 9.8])
    notifier = FakeReportNotifier()
    client = make_client(local_settings, notifier)

    first = generate(client, rows[-1]["date"])
    second = generate(client, rows[-1]["date"])

    assert first["delivered"] is True
    assert len(notifier.reports) == 1
    assert second["kept"] is True
    assert second["delivered"] is False
    assert second["report"] == first["report"]


def test_undelivered_draft_is_regenerated(local_settings, tmp_path):
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10, 9.8])
    client = make_client(local_settings, SilentNotifier())

    first = generate(client, rows[-1]["date"])
    second = generate(client, rows[-1]["date"])

    assert first["kept"] is False
    assert second["kept"] is False
    assert second["reason"] == "通知通道尚未配置"


def test_push_failure_still_returns_content(local_settings, tmp_path):
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10, 9.8])

    data = generate(make_client(local_settings, FakeReportNotifier(explode=True)), rows[-1]["date"])

    assert data["delivered"] is False
    assert data["report"]["tradeDate"] == rows[-1]["date"]
    assert "通道挂了" in data["reason"]


def test_failed_push_leaves_draft_for_retry(local_settings, tmp_path):
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10, 9.8])
    failing = FakeReportNotifier(ok=False)
    client = make_client(local_settings, failing)

    first = generate(client, rows[-1]["date"])
    second = generate(client, rows[-1]["date"])

    assert first["delivered"] is False
    assert second["kept"] is False  # 没投递成功，仍是草稿，允许再试


def test_list_shows_dates_desc(local_settings, tmp_path):
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10])
    client = make_client(local_settings)
    generate(client, rows[0]["date"])
    generate(client, rows[-1]["date"])

    data = client.get("/api/v1/reports").json()["data"]

    assert data["total"] == 2
    assert [item["tradeDate"] for item in data["items"]] == [rows[-1]["date"], rows[0]["date"]]
    assert data["items"][0]["triggerCount"] == 0


def test_detail_returns_content(local_settings, tmp_path):
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10])
    client = make_client(local_settings)
    generate(client, rows[-1]["date"])

    data = client.get(f"/api/v1/reports/{rows[-1]['date']}").json()["data"]

    assert data["report"]["tradeDate"] == rows[-1]["date"]
    assert data["disclaimer"] == notify.DISCLAIMER


def test_detail_missing_date_is_404(local_settings):
    response = make_client(local_settings).get("/api/v1/reports/2026-01-01")

    assert response.status_code == 404


def test_bad_date_is_400(local_settings):
    client = make_client(local_settings)

    assert client.post("/api/v1/reports/generate", json={"date": "2026/01/01"}).status_code == 400
    assert client.get("/api/v1/reports/2026-13-01").status_code == 400


def test_bad_paging_is_400(local_settings):
    client = make_client(local_settings)

    assert client.get("/api/v1/reports", params={"page": 0}).status_code == 400
    assert client.get("/api/v1/reports", params={"pageSize": 0}).status_code == 400


def test_report_text_is_self_contained(local_settings, tmp_path):
    rows, rule_id = seed(local_settings, tmp_path, [10, 10, 10, 9.8])
    add_trigger(local_settings, rule_id, rows[-1]["date"])
    content = generate(make_client(local_settings), rows[-1]["date"])["report"]

    text = notify.report_text(content)

    assert rows[-1]["date"] in text
    assert CODE in text
    assert "均线 2 日" in text
    assert "不构成投资建议" in text


def test_report_text_says_no_trigger_explicitly(local_settings, tmp_path):
    rows, _ = seed(local_settings, tmp_path, [10, 10, 10])

    text = notify.report_text(generate(make_client(local_settings), rows[-1]["date"])["report"])

    assert "无" in text


def test_report_subject_carries_count(local_settings, tmp_path):
    rows, rule_id = seed(local_settings, tmp_path, [10, 10, 10, 9.8])
    add_trigger(local_settings, rule_id, rows[-1]["date"])

    content = generate(make_client(local_settings), rows[-1]["date"])["report"]

    assert notify.report_subject(content) == f"{rows[-1]['date']} 收盘日报（1 条触发）"
