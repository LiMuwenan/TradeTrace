# -*- coding: utf-8 -*-
"""通知通道：正文自足、ntfy→邮件降级、投递记录，以及每日上限的计数口径。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from app.services import notify, rule_eval
from app.services.notify import AlertNotifier, PushOutcome
from app.storage import meta_db, notify_store, rule_store

CODE = "sh.600000"

ALERT = {
    "id": 1,
    "code": CODE,
    "name": "浦发银行",
    "ruleId": 3,
    "ruleType": "breakout",
    "ruleName": "突破 60 日",
    "value": 12.10,
    "threshold": None,
    "price": 12.30,
    "window": 60,
    "tradeDate": "2026-06-11",
}


def save_config(local_settings, **fields):
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        notify_store.save_config(conn, fields, timezone=local_settings.timezone)
    finally:
        conn.close()


def logs(local_settings) -> list:
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        return conn.execute("SELECT * FROM notification_log ORDER BY id").fetchall()
    finally:
        conn.close()


@pytest.fixture
def alert(local_settings) -> dict:
    """一条真实存在的预警（notification_log 对事件行有外键）。"""
    return {**ALERT, "id": seed_pending(local_settings, 1)[0]}


def test_alert_text_is_self_contained():
    text = notify.alert_text(ALERT)

    assert CODE in text
    assert "浦发银行" in text
    assert "突破 60 日" in text
    assert "12.30" in text  # 判定价
    assert "12.10" in text  # 指标值
    assert "2026-06-11" in text
    assert "不构成投资建议" in text


@pytest.mark.parametrize(
    "rule_type, expected",
    [
        ("oversold", "回落"),
        ("volume_surge", "量比"),
        ("volume_shrink", "量比"),
        ("ma_cross", "均线"),
        ("breakout", "前 60 日最高"),
    ],
)
def test_alert_text_describes_each_rule_type(rule_type, expected):
    text = notify.alert_text({**ALERT, "ruleType": rule_type, "threshold": 20.0})

    assert expected in text


def test_ntfy_success_writes_ok_log(local_settings, alert):
    save_config(local_settings, ntfy_topic="long-random-topic")
    sent: list[dict] = []
    notifier = AlertNotifier(
        local_settings,
        ntfy_sender=lambda config, alert: sent.append(alert),
    )

    outcome = notifier.send(alert)

    assert outcome == PushOutcome(ok=True, channel="ntfy")
    assert len(sent) == 1
    rows = logs(local_settings)
    assert len(rows) == 1
    assert rows[0]["result"] == "ok"
    assert rows[0]["channel"] == "ntfy"
    assert rows[0]["event_id"] == alert["id"]


def test_ntfy_failure_falls_back_to_email(local_settings, alert):
    save_config(
        local_settings,
        ntfy_topic="long-random-topic",
        smtp_host="smtp.example.com",
        smtp_port=465,
        email_to="me@example.com",
    )

    def broken(config, alert):
        raise TimeoutError("ntfy 超时")

    mails: list[dict] = []
    notifier = AlertNotifier(
        local_settings,
        ntfy_sender=broken,
        email_sender=lambda config, alert: mails.append(alert),
    )

    outcome = notifier.send(alert)

    assert outcome.ok is True
    assert outcome.channel == "email"
    assert len(mails) == 1
    row = logs(local_settings)[0]
    assert row["result"] == "fallback"
    assert row["channel"] == "email"
    assert "ntfy 超时" in row["detail"]


def test_both_channels_failing_is_recorded_as_failed(local_settings, alert):
    save_config(
        local_settings,
        ntfy_topic="long-random-topic",
        smtp_host="smtp.example.com",
        email_to="me@example.com",
    )

    def broken(config, alert):
        raise TimeoutError("连不上")

    notifier = AlertNotifier(local_settings, ntfy_sender=broken, email_sender=broken)

    outcome = notifier.send(alert)

    assert outcome.ok is False
    assert "ntfy" in outcome.error and "邮件" in outcome.error
    row = logs(local_settings)[0]
    assert row["result"] == "failed"
    assert row["channel"] is None


def test_unconfigured_notifier_sends_nothing(local_settings, alert):
    notifier = AlertNotifier(local_settings)

    assert notifier.configured is False
    outcome = notifier.send(alert)

    assert outcome.ok is False
    assert outcome.error == "未配置任何通知通道"
    assert logs(local_settings)[0]["result"] == "failed"


def test_email_only_config_is_ready(local_settings, alert):
    save_config(local_settings, smtp_host="smtp.example.com", email_to="me@example.com")
    notifier = AlertNotifier(
        local_settings, email_sender=lambda config, alert: None
    )

    assert notifier.configured is True
    assert notifier.send(alert).channel == "email"
    assert logs(local_settings)[0]["result"] == "ok"


def test_test_notification_does_not_consume_quota(local_settings):
    save_config(local_settings, ntfy_topic="long-random-topic")
    notifier = AlertNotifier(local_settings, ntfy_sender=lambda config, alert: None)

    notifier.send_test(notify.build_test_alert(local_settings))

    assert len(logs(local_settings)) == 1
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        assert notify_store.attempted_ids(conn, "2026-06-11") == set()
    finally:
        conn.close()


# --- 每日上限 -------------------------------------------------------------


class CountingNotifier:
    configured = True

    def __init__(self) -> None:
        self.sent: list[int] = []

    def send(self, alert: dict) -> PushOutcome:
        self.sent.append(alert["id"])
        return PushOutcome(ok=True, channel="fake")


def seed_pending(local_settings, count: int, trade_date: str = "2026-06-11") -> list[int]:
    """造 count 条待推送的预警，返回它们的 id。"""
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        rule = rule_store.create_rule(conn, type="breakout", name="突破", window=60)
        ids = []
        for index in range(count):
            rule_store.record_event(
                conn,
                code=f"sh.60{index:04d}",
                rule_id=rule.id,
                trade_date=trade_date,
                event="enter",
                value=12.0,
                price=12.1,
            )
            ids.append(int(rule_store.last_event(conn, f"sh.60{index:04d}", rule.id)["id"]))
        return ids
    finally:
        conn.close()


def test_daily_limit_skips_excess_alerts(local_settings):
    save_config(local_settings, ntfy_topic="topic", daily_limit=2)
    seed_pending(local_settings, 5)
    notifier = CountingNotifier()

    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        summary = rule_eval._push_pending(conn, local_settings, "2026-06-11", notifier)
    finally:
        conn.close()

    assert len(notifier.sent) == 2
    assert summary["attempted"] == 2
    assert summary["succeeded"] == 2
    assert summary["skipped"] == 3


def test_limit_disabled_sends_everything(local_settings):
    save_config(local_settings, ntfy_topic="topic", daily_limit=2, limit_enabled=False)
    seed_pending(local_settings, 5)
    notifier = CountingNotifier()

    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        summary = rule_eval._push_pending(conn, local_settings, "2026-06-11", notifier)
    finally:
        conn.close()

    assert len(notifier.sent) == 5
    assert summary["skipped"] == 0


def test_rerun_after_partial_failure_does_not_double_count(local_settings):
    """已尝试过的预警重跑时不再占用新额度（同一交易日、同一条预警）。"""
    save_config(local_settings, ntfy_topic="topic", daily_limit=2)
    seed_pending(local_settings, 3, trade_date="2026-06-11")
    conn = meta_db.connect(local_settings.meta_dir, local_settings.timezone)
    try:
        # 前两条已经尝试过但失败（没有 pushed_at），额度已用满
        for row in rule_store.pending_alerts(conn, "2026-06-11")[:2]:
            notify_store.log_attempt(
                conn,
                event_id=int(row["id"]),
                trade_date="2026-06-11",
                channel=None,
                result=notify_store.RESULT_FAILED,
                detail="上次失败",
                timezone=local_settings.timezone,
            )
        notifier = CountingNotifier()
        summary = rule_eval._push_pending(conn, local_settings, "2026-06-11", notifier)
    finally:
        conn.close()

    # 已尝试过的两条允许重试，第三条因额度已满被跳过
    assert len(notifier.sent) == 2
    assert summary["skipped"] == 1


# --- 设置接口 -------------------------------------------------------------


def make_client(local_settings) -> TestClient:
    return TestClient(create_app(local_settings))


def test_read_config_masks_credentials(local_settings):
    save_config(
        local_settings,
        ntfy_topic="topic-abc",
        ntfy_token="tk-secret",
        smtp_host="smtp.example.com",
        smtp_password="pwd-secret",
        email_to="me@example.com",
    )
    client = make_client(local_settings)

    data = client.get("/api/v1/settings/notification").json()["data"]

    assert "tk-secret" not in str(data)
    assert "pwd-secret" not in str(data)
    assert data["ntfyTokenConfigured"] is True
    assert data["smtpPasswordConfigured"] is True
    assert data["ntfyTopic"] == "topic-abc"  # 主题名要给手机端订阅用，不能藏
    assert data["configured"] is True
    assert data["usage"]["limit"] == 50


def test_update_saves_and_keeps_untouched_fields(local_settings):
    client = make_client(local_settings)
    client.put(
        "/api/v1/settings/notification",
        json={"ntfyServer": "https://ntfy.example.com", "ntfyTopic": "topic-abc", "smtpPassword": "pwd"},
    )

    data = client.put(
        "/api/v1/settings/notification", json={"dailyLimit": 30}
    ).json()["data"]

    assert data["dailyLimit"] == 30
    assert data["ntfyTopic"] == "topic-abc"
    assert data["smtpPasswordConfigured"] is True


def test_update_with_empty_string_clears_field(local_settings):
    client = make_client(local_settings)
    client.put("/api/v1/settings/notification", json={"ntfyTopic": "topic-abc"})

    data = client.put("/api/v1/settings/notification", json={"ntfyTopic": ""}).json()["data"]

    assert data["ntfyTopic"] is None
    assert data["configured"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"ntfyServer": "ntfy.example.com"},
        {"emailTo": "not-an-email"},
        {"smtpPort": 0},
        {"smtpPort": 70000},
        {"dailyLimit": 0},
        {"dailyLimit": 1001},
    ],
)
def test_invalid_config_is_400(local_settings, payload):
    client = make_client(local_settings)

    response = client.put("/api/v1/settings/notification", json=payload)

    assert response.status_code == 400
    assert response.json()["code"] == 400


def test_test_notification_reports_missing_channel(local_settings):
    client = make_client(local_settings)

    data = client.post("/api/v1/settings/notification/test").json()["data"]

    assert data["ok"] is False
    assert "尚未配置" in data["error"]


def test_log_endpoint_lists_attempts(local_settings, alert):
    save_config(local_settings, ntfy_topic="topic")
    AlertNotifier(local_settings, ntfy_sender=lambda c, a: None).send(alert)
    client = make_client(local_settings)

    data = client.get("/api/v1/notifications/log").json()["data"]

    assert data["total"] == 1
    item = data["items"][0]
    assert item["result"] == "ok"
    assert item["channel"] == "ntfy"
    assert item["tradeDate"] == "2026-06-11"


def test_log_endpoint_rejects_bad_paging(local_settings):
    client = make_client(local_settings)

    assert client.get("/api/v1/notifications/log", params={"page": 0}).status_code == 400
    assert client.get("/api/v1/notifications/log", params={"pageSize": 0}).status_code == 400
