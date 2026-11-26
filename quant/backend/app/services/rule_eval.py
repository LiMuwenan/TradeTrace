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
from app.storage import notify_store, rule_store
from app.storage.meta_db import MA_RULE_TYPES, Rule, connect
from app.storage.parquet_store import ParquetStore
from app.storage.schema import normalize_code
from app.storage.stock_names import StockNameCache
from app.storage.watchlist_store import load_watchlist

logger = logging.getLogger(__name__)


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
    return rule.window - 1 if rule.type in MA_RULE_TYPES else rule.window


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
    if rule.type in MA_RULE_TYPES:
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


def next_event(state: str | None, signal: Signal) -> str | None:
    """当前状态 + 当日判定 → 该记录的事件；状态没变则返回 None。

    起点视为「未触发」，所以第一次满足就是 enter，第一次不满足不产生 exit。
    """
    if signal.satisfied:
        return None if state == "enter" else "enter"
    return "exit" if state == "enter" else None


def is_near(rule: Rule, signal: Signal | None) -> bool:
    """未触发但与阈值的差距在 20% 以内（票面「接近阈值」），供 09 日报使用，本票不展示。"""
    if signal is None or signal.satisfied or signal.value is None:
        return False
    threshold = rule.threshold or 0.0
    if rule.type == "oversold":
        return signal.value >= threshold * 0.8
    if rule.type == "volume_surge":
        return signal.value >= threshold * 0.8
    if rule.type == "volume_shrink":
        return signal.value <= threshold * 1.2
    if rule.type in ("breakout", "ma_cross"):
        level = signal.value
        return level > 0 and (level - (signal.price or 0.0)) / level <= 0.2
    return False


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
        event = next_event(state, signal)
        if event is None:
            continue
        state = event
        events.append(
            Transition(index=index, date=bars[index]["date"], event=event, signal=signal)
        )
    return events


def scope_codes(settings: Settings, rule: Rule, cache: dict[str, list[str]]) -> list[str]:
    """规则实际覆盖的标的。日报与求值共用同一套范围判定。"""
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

        debug_code = normalize_code(code) if code else None  # 非法代码抛 IngestError，由路由转 400

        for rule in rules:
            if debug_code:
                # 调试代码只覆盖「全部自选」；指定单只的规则仍只算自己那只
                if rule.scope == "single" and rule.scope_code != debug_code:
                    continue
                codes = [debug_code]
            else:
                codes = scope_codes(settings, rule, scope_cache)

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

                state = rule_store.current_state(conn, item, rule.id)
                event = next_event(state, signal)
                if event is None:
                    continue
                inserted = rule_store.record_event(
                    conn,
                    code=item,
                    rule_id=rule.id,
                    trade_date=trade_date,
                    event=event,
                    value=signal.value,
                    threshold=signal.threshold,
                    price=signal.price,
                    timezone=settings.timezone,
                )
                if inserted:
                    entered += 1 if event == "enter" else 0
                    exited += 1 if event == "exit" else 0

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
    """把当日待投递的预警交给通知通道。失败只记录，不影响求值结果（ADR 0008）。

    每日上限按交易日计「尝试投递的条数」（ADR 0009）：超限的行不标记 `pushed_at`，
    仍留在库里由 07 的列表展示。
    """
    pending = rule_store.pending_alerts(conn, trade_date)
    if not notifier.configured:
        return {"attempted": 0, "succeeded": 0, "failed": 0, "skipped": len(pending),
                "reason": "通知通道尚未配置"}

    limit = notify_store.load_config(conn).effective_limit()
    used = notify_store.attempted_ids(conn, trade_date)
    names = StockNameCache(settings.meta_dir).names()

    succeeded = 0
    failed = 0
    skipped = 0
    for row in pending:
        alert = _alert_payload(row, names)
        if limit is not None and alert["id"] not in used and len(used) >= limit:
            skipped += 1
            continue
        used.add(alert["id"])
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
    return {
        "attempted": succeeded + failed,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
    }


def _alert_payload(row, names: dict[str, str]) -> dict:
    """一条预警交给通知通道的形状。名称缺失时只给代码，不编造。"""
    return {
        "id": int(row["id"]),
        "code": row["code"],
        "name": names.get(row["code"], ""),
        "tradeDate": row["trade_date"],
        "ruleId": row["rule_id"],
        "ruleType": row["rule_type"],
        "ruleName": row["rule_name"],
        "value": row["value"],
        "threshold": row["threshold"],
        "price": row["price"],
        "window": row["rule_window"],
    }


def replay_rule(settings: Settings, rule_id: int, *, until: str | None = None) -> dict:
    """静默回放：从该规则能算出结果的最早一天走到 `until` 的前一日，只写记录不推送。

    `until` 缺省取规则创建日（新建规则时即今天）。重新启用已停用的规则时由调用方
    传入启用日，把停用期间漏掉的历史一并补上。

    起点必须早到足以看见「由假变真」的那一刻：若只从「距今 N 个交易日」起算，而条件
    在整段窗口内一直成立，回放就看不到进入点，触发态会被误判为未触发，次日求值立刻
    产生一条假预警。代价是回放覆盖全历史，「历史触发次数」按 ADR 0007 的口径统计。
    """
    store = ParquetStore(settings.parquet_dir)
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        rule = rule_store.get_rule(conn, rule_id)
        if rule is None:
            raise LookupError(f"规则不存在：{rule_id}")

        enabled_on = until or rule.created_at[:10]
        scope_cache: dict[str, list[str]] = {}
        codes = scope_codes(settings, rule, scope_cache)
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
            for transition in transitions(rule, bars, end_index=end_index):
                inserted = rule_store.record_event(
                    conn,
                    code=code,
                    rule_id=rule.id,
                    trade_date=transition.date,
                    event=transition.event,
                    value=transition.signal.value,
                    threshold=transition.signal.threshold,
                    price=transition.signal.price,
                    replayed=True,
                    timezone=settings.timezone,
                )
                if inserted:
                    entered += 1 if transition.event == "enter" else 0
                    exited += 1 if transition.event == "exit" else 0

        return {
            "ruleId": rule.id,
            "codes": touched,
            "entered": entered,
            "exited": exited,
        }
    finally:
        conn.close()


def history_for(settings: Settings, rule_id: int, code: str) -> dict:
    """某标的某规则的触发历史：何时进入触发态、何时解除。"""
    normalized = normalize_code(code)
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        rule = rule_store.get_rule(conn, rule_id)
        if rule is None:
            raise LookupError(f"规则不存在：{rule_id}")
        items = [
            {
                "tradeDate": row["trade_date"],
                "event": row["event"],
                "value": row["value"],
                "threshold": row["threshold"],
                "price": row["price"],
                "reason": row["reason"],
                "replayed": bool(row["replayed"]),
                "pushedAt": row["pushed_at"],
                "readAt": row["read_at"],
            }
            for row in rule_store.history(conn, rule_id, normalized)
        ]
        state = rule_store.current_state(conn, normalized, rule_id)
    finally:
        conn.close()
    return {
        "rule": rule.as_dict(),
        "code": normalized,
        "state": state,
        "items": items,
        "count": len(items),
    }
