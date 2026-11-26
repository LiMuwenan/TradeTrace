# -*- coding: utf-8 -*-
"""规则定义与变更记录的存储契约：建表幂等、参数校验、事件唯一键。"""
from __future__ import annotations

import sqlite3

import pytest

from app.storage import meta_db, rule_store
from app.storage.meta_db import RuleValidationError


def _conn(tmp_path) -> sqlite3.Connection:
    return meta_db.connect(tmp_path / "meta")


def test_connect_creates_schema_and_is_idempotent(tmp_path):
    first = _conn(tmp_path)
    rule_store.create_rule(first, type="breakout", name="突破60", window=60)
    first.close()

    second = _conn(tmp_path)
    tables = {
        row["name"]
        for row in second.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"alert_rule", "rule_state_event"} <= tables
    assert [rule.name for rule in rule_store.list_rules(second)] == ["突破60"]
    second.close()


def test_create_rule_defaults_and_scope_normalization(tmp_path):
    conn = _conn(tmp_path)

    rule = rule_store.create_rule(
        conn, type="breakout", name="浦发突破", scope="single", scope_code="600000", window=60
    )

    assert rule.scope == "single"
    assert rule.scope_code == "sh.600000"
    assert rule.threshold is None
    assert rule.enabled is True


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"type": "unknown", "window": 10}, "未知的规则类型"),
        ({"type": "breakout", "window": 1}, "时间窗不得小于 2"),
        ({"type": "oversold", "window": 60, "threshold": None}, "必须给出阈值"),
        ({"type": "oversold", "window": 60, "threshold": 120}, "超跌阈值"),
        ({"type": "volume_surge", "window": 5, "threshold": 0}, "量比阈值"),
        ({"type": "breakout", "window": 60, "scope": "single"}, "必须给出标的代码"),
        ({"type": "breakout", "window": 60, "scope": "all"}, "未知的标的范围"),
    ],
)
def test_invalid_rule_is_rejected(tmp_path, kwargs, message):
    conn = _conn(tmp_path)
    payload = {"name": "x", "type": "breakout", "window": 60} | kwargs

    with pytest.raises(RuleValidationError, match=message):
        rule_store.create_rule(conn, **payload)


def test_list_rules_filters_disabled(tmp_path):
    conn = _conn(tmp_path)
    rule_store.create_rule(conn, type="breakout", name="a", window=60)
    rule_store.create_rule(conn, type="ma_cross", name="b", window=20, enabled=False)

    assert [rule.name for rule in rule_store.list_rules(conn)] == ["a", "b"]
    assert [rule.name for rule in rule_store.list_rules(conn, enabled_only=True)] == ["a"]


def test_event_unique_key_makes_rerun_idempotent(tmp_path):
    conn = _conn(tmp_path)
    rule = rule_store.create_rule(conn, type="breakout", name="a", window=60)

    first = rule_store.record_event(
        conn, code="sh.600000", rule_id=rule.id, trade_date="2026-06-15", event="enter", price=10.0
    )
    second = rule_store.record_event(
        conn, code="sh.600000", rule_id=rule.id, trade_date="2026-06-15", event="enter", price=11.0
    )

    assert first is True
    assert second is False
    rows = conn.execute("SELECT price FROM rule_state_event").fetchall()
    assert [row["price"] for row in rows] == [10.0]


def test_current_state_follows_last_event(tmp_path):
    conn = _conn(tmp_path)
    rule = rule_store.create_rule(conn, type="ma_cross", name="ma20", window=20)

    assert rule_store.current_state(conn, "sh.600000", rule.id) is None
    rule_store.record_event(
        conn, code="sh.600000", rule_id=rule.id, trade_date="2026-06-15", event="enter"
    )
    assert rule_store.current_state(conn, "sh.600000", rule.id) == "enter"

    rule_store.record_event(
        conn, code="sh.600000", rule_id=rule.id, trade_date="2026-06-16", event="exit"
    )
    assert rule_store.current_state(conn, "sh.600000", rule.id) == "exit"


def test_close_states_writes_reasoned_exit_for_entered_codes(tmp_path):
    conn = _conn(tmp_path)
    rule = rule_store.create_rule(conn, type="ma_cross", name="ma20", window=20)
    rule_store.record_event(
        conn, code="sh.600000", rule_id=rule.id, trade_date="2026-06-15", event="enter"
    )
    rule_store.record_event(
        conn, code="sz.000001", rule_id=rule.id, trade_date="2026-06-15", event="enter"
    )
    rule_store.record_event(
        conn, code="sz.000001", rule_id=rule.id, trade_date="2026-06-16", event="exit"
    )

    closed = rule_store.close_states(conn, rule.id, reason="rule_disabled")

    assert closed == ["sh.600000"]
    assert rule_store.current_state(conn, "sh.600000", rule.id) == "exit"
    last = rule_store.last_event(conn, "sh.600000", rule.id)
    assert last["reason"] == "rule_disabled"
    assert last["trade_date"] == "2026-06-15"  # 与当日 enter 同日，靠唯一键含 event 才写得进去


def test_update_rule_rewrites_params_but_keeps_type_and_scope(tmp_path):
    conn = _conn(tmp_path)
    rule = rule_store.create_rule(
        conn, type="breakout", name="旧名", scope="single", scope_code="sh.600000", window=60
    )

    updated = rule_store.update_rule(conn, rule.id, name="新名", window=20, threshold=None)

    assert updated is not None
    assert (updated.name, updated.window) == ("新名", 20)
    assert (updated.type, updated.scope, updated.scope_code) == ("breakout", "single", "sh.600000")


def test_update_rule_rejects_out_of_range_window(tmp_path):
    conn = _conn(tmp_path)
    rule = rule_store.create_rule(conn, type="breakout", name="a", window=60)

    with pytest.raises(rule_store.RuleValidationError):
        rule_store.update_rule(conn, rule.id, name="a", window=1, threshold=None)


def test_update_rule_validates_threshold_with_existing_type(tmp_path):
    """改参数沿用原类型的阈值口径：超跌规则漏给阈值必须报错，而不是静默清空。"""
    conn = _conn(tmp_path)
    rule = rule_store.create_rule(conn, type="oversold", name="a", window=60, threshold=20.0)

    with pytest.raises(rule_store.RuleValidationError):
        rule_store.update_rule(conn, rule.id, name="a", window=30, threshold=None)


def test_last_enter_dates_ignores_replayed_records(tmp_path):
    conn = _conn(tmp_path)
    rule = rule_store.create_rule(conn, type="breakout", name="a", window=2)
    rule_store.record_event(conn, code="sh.600000", rule_id=rule.id, trade_date="2026-06-01", event="enter", replayed=True)
    rule_store.record_event(conn, code="sh.600000", rule_id=rule.id, trade_date="2026-06-03", event="enter")

    assert rule_store.last_enter_dates(conn) == {rule.id: "2026-06-03"}
