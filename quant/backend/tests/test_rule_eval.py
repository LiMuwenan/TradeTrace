# -*- coding: utf-8 -*-
"""四类规则的判定口径与边沿触发状态机。

口径（05 票）：跨日比较一律用后复权价；量比的均量不含当日；停牌行不参与窗口计算。
"""
from __future__ import annotations

import pytest

from app.services import rule_eval
from app.storage.meta_db import Rule
from factories import adj_bars


def make_rule(type: str, window: int, threshold: float | None = None) -> Rule:
    return Rule(
        id=1,
        type=type,
        name=type,
        scope="watchlist",
        scope_code=None,
        window=window,
        threshold=threshold,
        enabled=True,
        created_at="2026-01-01T00:00:00+08:00",
    )


def test_trading_bars_drops_suspended_rows():
    bars = adj_bars([10, 999, 11], tradestatus=[1, 0, 1])

    kept = rule_eval.trading_bars(bars)

    assert [bar["adjClose"] for bar in kept] == [10, 11]


def test_breakout_needs_full_window():
    rule = make_rule("breakout", 3)
    bars = adj_bars([10, 10])

    assert rule_eval.signal_at(rule, bars, len(bars) - 1) is None


def test_breakout_compares_with_previous_high_excluding_today():
    rule = make_rule("breakout", 3)
    bars = adj_bars([10, 12, 11, 12.5])

    signal = rule_eval.signal_at(rule, bars, 3)

    assert signal is not None
    assert signal.satisfied is True
    assert signal.value == 12  # 前 3 日最高收盘，不含当日
    assert signal.price == 12.5


def test_oversold_reports_drop_percent():
    rule = make_rule("oversold", 3, threshold=20)
    bars = adj_bars([10, 10, 10, 7.5])

    signal = rule_eval.signal_at(rule, bars, 3)

    assert signal is not None
    assert signal.satisfied is True
    assert signal.value == pytest.approx(25.0)
    assert signal.threshold == 20


def test_oversold_not_triggered_below_threshold():
    rule = make_rule("oversold", 3, threshold=20)
    bars = adj_bars([10, 10, 10, 9.0])

    signal = rule_eval.signal_at(rule, bars, 3)

    assert signal is not None
    assert signal.satisfied is False


def test_volume_surge_average_excludes_today():
    rule = make_rule("volume_surge", 2, threshold=1.5)
    bars = adj_bars([10, 10, 10, 10], volumes=[100, 100, 400, 400])

    signal = rule_eval.signal_at(rule, bars, 2)

    assert signal is not None
    # 前 2 日均量 100，当日 400 → 量比 4.0，不是 400/250
    assert signal.value == pytest.approx(4.0)
    assert signal.satisfied is True


def test_volume_shrink_triggers_on_low_ratio():
    rule = make_rule("volume_shrink", 2, threshold=0.6)
    bars = adj_bars([10, 10, 10], volumes=[100, 100, 40])

    signal = rule_eval.signal_at(rule, bars, 2)

    assert signal is not None
    assert signal.satisfied is True


def test_ma_cross_uses_mean_including_today():
    rule = make_rule("ma_cross", 3)
    bars = adj_bars([10, 10, 10, 11])

    signal = rule_eval.signal_at(rule, bars, 3)

    assert signal is not None
    assert signal.value == pytest.approx(10.3333, rel=1e-3)
    assert signal.satisfied is True


def test_edge_transitions_only_on_change():
    rule = make_rule("ma_cross", 2)
    bars = adj_bars([10, 10, 10, 12, 13, 10, 13])

    events = rule_eval.transitions(rule, bars)

    assert [(item.index, item.event) for item in events] == [
        (3, "enter"),
        (5, "exit"),
        (6, "enter"),
    ]


def test_transitions_skip_suspended_days_without_changing_state():
    rule = make_rule("ma_cross", 2)
    # 第 4 行停牌（价格被排除），恢复后价格仍高于均线，不应产生新事件
    bars = adj_bars([10, 10, 12, 999, 13], tradestatus=[1, 1, 1, 0, 1])

    events = rule_eval.transitions(rule, bars)

    assert [(item.index, item.event) for item in events] == [(2, "enter")]


def test_transitions_start_index_drops_earlier_events():
    rule = make_rule("ma_cross", 2)
    bars = adj_bars([10, 10, 10, 12, 13])

    events = rule_eval.transitions(rule, bars, start_index=3)

    assert [(item.index, item.event) for item in events] == [(3, "enter")]
