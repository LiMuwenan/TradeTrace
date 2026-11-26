# -*- coding: utf-8 -*-
"""规则求值：四类条件的判定、边沿触发状态机，以及按交易日／按规则回放的落库。

口径（05 票 + ADR 0007）：
- 跨日比较一律使用后复权价（`adjClose`），停牌行不参与窗口；
- 触发态不落库，由 `rule_state_event` 的最后一条事件推导；
- 同一交易日重复求值依靠唯一键幂等；
- 求值结束后同步调用通知（ADR 0008），失败不影响已写入的记录。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import fmean
from typing import Iterable

from app.config import Settings
from app.services.notify import Notifier, NullNotifier
from app.storage import rule_store
from app.storage.meta_db import Rule, connect
from app.storage.parquet_store import ParquetStore
from app.storage.schema import IngestError, normalize_code
from app.storage.watchlist_store import load_watchlist

logger = logging.getLogger(__name__)

MA_TYPES = ("ma_cross",)


@dataclass(frozen=True)
class Signal:
    """某一交易日的判定结果。`value` 是指标值，`price` 是判定所用的后复权价。"""

    satisfied: bool
    value: float | None
    threshold: float | None
    price: float | None


@dataclass(frozen=True)
class Transition:
    index: int
    date: str
    event: str
    signal: Signal


def trading_bars(bars: Iterable[dict]) -> list[dict]:
    """只保留可参与计算的交易日：非停牌且后复权价齐全。"""
    return [
        bar
        for bar in bars
        if int(bar.get("tradestatus", 1)) == 1 and bar.get("adjClose") is not None
    ]


def first_index(rule: Rule) -> int:
    """该规则能算出结果的最早下标。回放起点就取这里，不必回溯到数据起点。"""
    return rule.window - 1 if rule.type in MA_TYPES else rule.window


def signal_at(rule: Rule, bars: list[dict], index: int) -> Signal | None:
    """计算 `index` 处的判定结果；窗口不足或数据不完整时返回 None。"""
    if index < 0 or index >= len(bars):
        return None
    close = bars[index].get("adjClose")
    if close is None:
        return None
    start = first_index(rule)
    if index < start:
        return None

    window = rule.window
    if rule.type in MA_TYPES:
        window_bars = bars[index - window + 1 : index + 1]
        mean = fmean(bar["adjClose"] for bar in window_bars)
        return Signal(satisfied=close > mean, value=round(mean, 4), threshold=None, price=close)

    previous = bars[index - window : index]
    if rule.type == "breakout":
        highest = max(bar["adjClose"] for bar in previous)
        return Signal(satisfied=close > highest, value=highest, threshold=None, price=close)

    if rule.type == "oversold":
        highest = max(bar["adjClose"] for bar in previous)
        if highest <= 0:
            return None
        drop = (highest - close) / highest * 100
        return Signal(
            satisfied=drop >= (rule.threshold or 0.0),
            value=round(drop, 4),
            threshold=rule.threshold,
            price=close,
        )

    if rule.type in ("volume_surge", "volume_shrink"):
        volumes = [bar.get("volume") for bar in previous]
        if any(volume is None for volume in volumes):
            return None
        average = fmean(volumes)  # type: ignore[arg-type]
        today = bars[index].get("volume")
        if average <= 0 or today is None:
            return None
        ratio = today / average
        threshold = rule.threshold or 0.0
        satisfied = ratio >= threshold if rule.type == "volume_surge" else ratio <= threshold
        return Signal(satisfied=satisfied, value=round(ratio, 4), threshold=rule.threshold, price=close)

    return None


def transitions(
    rule: Rule, bars: list[dict], *, start_index: int | None = None, end_index: int | None = None
) -> list[Transition]:
    """从 `start_index` 走到 `end_index`，逐日判定并产出状态变化。

    起点之前视为「未触发」。判定为 None 的交易日（停牌、窗口不足）不改变状态。
    """
    start = first_index(rule) if start_index is None else start_index
    bars = trading_bars(bars)
    end = len(bars) - 1 if end_index is None else min(end_index, len(bars) - 1)
    events: list[Transition] = []
    state: str | None = None
    for index in range(max(start, 0), end + 1):
        signal = signal_at(rule, bars, index)
        if signal is None:
            continue
        desired = "enter" if signal.satisfied else "exit"
        if desired == state:
            continue
        if state is None and desired == "exit":
            state = "exit"
            continue
        state = desired
        events.append(
            Transition(index=index, date=bars[index]["date"], event=desired, signal=signal)
        )
    return events


def _scope_codes(settings: Settings, rule: Rule, cache: dict[str, list[str]]) -> list[str]:
    if rule.scope == "single":
        return [rule.scope_code] if rule.scope_code else []
    if "watchlist" not in cache:
        cache["watchlist"] = [entry.code for entry in load_watchlist(settings.meta_dir)]
    return cache["watchlist"]


def evaluate_day(
    settings: Settings,
    trade_date: str,
    *,
    code: str | None = None,
    notifier: Notifier | None = None,
) -> dict:
    """对指定交易日求值，落库后同步推送待投递的预警。"""
    notifier = notifier or NullNotifier()
    store = ParquetStore(settings.parquet_dir)
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        rules = rule_store.list_rules(conn, enabled_only=True)
        scope_cache: dict[str, list[str]] = {}
        series_cache: dict[str, list[dict]] = {}
        evaluated = 0
        entered = 0
        exited = 0

        debug_code = normalize_code(code) if code else None

        for rule in rules:
            codes = [debug_code] if debug_code else _scope_codes(settings, rule, scope_cache)
            for item in codes:
                if item not in series_cache:
                    series_cache[item] = trading_bars(store.series(item, None, trade_date))
                bars = series_cache[item]
                if not bars or bars[-1]["date"] != trade_date:
                    continue  # 当日停牌或没有数据，不参与求值，状态保持不变
                signal = signal_at(rule, bars, len(bars) - 1)
                if signal is None:
                    continue
                evaluated += 1

                desired = "enter" if signal.satisfied else "exit"
                state = rule_store.current_state(conn, item, rule.id)
                if state == desired or (state is None and desired == "exit"):
                    continue
                inserted = rule_store.record_event(
                    conn,
                    code=item,
                    rule_id=rule.id,
                    trade_date=trade_date,
                    event=desired,
                    value=signal.value,
                    threshold=signal.threshold,
                    price=signal.price,
                    timezone=settings.timezone,
                )
                if inserted:
                    entered += 1 if desired == "enter" else 0
                    exited += 1 if desired == "exit" else 0

        push = _push_pending(conn, settings, trade_date, notifier)
        return {
            "tradeDate": trade_date,
            "evaluated": evaluated,
            "entered": entered,
            "exited": exited,
            "push": push,
        }
    finally:
        conn.close()


def _push_pending(conn, settings: Settings, trade_date: str, notifier: Notifier) -> dict:
    """把当日待投递的预警交给通知通道。失败只记录，不影响求值结果（ADR 0008）。"""
    pending = rule_store.pending_alerts(conn, trade_date)
    if not notifier.configured:
        return {"attempted": 0, "succeeded": 0, "failed": 0, "skipped": len(pending),
                "reason": "通知通道尚未配置"}

    succeeded = 0
    failed = 0
    for row in pending:
        alert = {
            "id": row["id"],
            "code": row["code"],
            "tradeDate": row["trade_date"],
            "ruleId": row["rule_id"],
            "ruleType": row["rule_type"],
            "ruleName": row["rule_name"],
            "value": row["value"],
            "threshold": row["threshold"],
            "price": row["price"],
        }
        try:
            outcome = notifier.send(alert)
        except Exception as exc:  # 通知实现的任何异常都不得反向影响求值
            logger.warning("推送失败：%s（%s）", row["code"], exc)
            failed += 1
            continue
        if outcome.ok:
            rule_store.mark_pushed(
                conn, int(row["id"]), channel=outcome.channel or "unknown", timezone=settings.timezone
            )
            succeeded += 1
        else:
            logger.warning("推送失败：%s（%s）", row["code"], outcome.error)
            failed += 1
    return {"attempted": len(pending), "succeeded": succeeded, "failed": failed, "skipped": 0}


def replay_rule(settings: Settings, rule_id: int) -> dict:
    """静默回放：从该规则能算出结果的最早一天走到启用前一日，只写记录不推送。"""
    store = ParquetStore(settings.parquet_dir)
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        rule = rule_store.get_rule(conn, rule_id)
        if rule is None:
            raise LookupError(f"规则不存在：{rule_id}")

        enabled_on = rule.created_at[:10]
        scope_cache: dict[str, list[str]] = {}
        codes = _scope_codes(settings, rule, scope_cache)
        entered = 0
        exited = 0
        touched = 0

        for code in codes:
            bars = trading_bars(store.series(code, None, enabled_on))
            # 只回放到启用日之前，「启用当天」由正常求值负责
            end_index = max((i for i, bar in enumerate(bars) if bar["date"] < enabled_on), default=-1)
            if end_index < first_index(rule):
                continue
            touched += 1
            for item in transitions(rule, bars, end_index=end_index):
                inserted = rule_store.record_event(
                    conn,
                    code=code,
                    rule_id=rule.id,
                    trade_date=item.date,
                    event=item.event,
                    value=item.signal.value,
                    threshold=item.signal.threshold,
                    price=item.signal.price,
                    replayed=True,
                    timezone=settings.timezone,
                )
                if inserted:
                    entered += 1 if item.event == "enter" else 0
                    exited += 1 if item.event == "exit" else 0

        return {
            "ruleId": rule.id,
            "codes": touched,
            "entered": entered,
            "exited": exited,
        }
    finally:
        conn.close()
