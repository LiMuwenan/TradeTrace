# -*- coding: utf-8 -*-
"""规则定义的读写编排（06 号票）：列表聚合、新建、修改、启停。

三条纪律来自票面与 ADR 0007：
- **新建/启用前必须静默回放**，否则状态从「未触发」硬起，次日会炸出假预警；
- **改参数与停用必须先写 `exit` 收尾**，避免旧口径的「满足」被新口径沿用；
- **本模块是规则的唯一写入口**，05 的 TOML 种子导入已随本票上线删除。
"""
from __future__ import annotations

from app.config import Settings
from app.services import rule_eval
from app.storage import rule_store
from app.storage.meta_db import Rule, RuleValidationError, connect, now_iso
from app.storage.watchlist_store import load_watchlist

RULE_TYPE_LABELS = {
    "breakout": "突破",
    "oversold": "超跌",
    "volume_surge": "放量",
    "volume_shrink": "缩量",
    "ma_cross": "均线穿越",
}

SCOPE_LABELS = {"watchlist": "全部自选", "single": "指定单只"}

# 改这些字段会让旧口径的判定失效，必须写一条 exit 收尾
_CLOSING_FIELDS = ("window", "threshold")


def list_rules(settings: Settings) -> dict:
    """规则列表：附加覆盖标的数与最近一次真实触发日。"""
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        rules = rule_store.list_rules(conn)
        last_dates = rule_store.last_enter_dates(conn)
    finally:
        conn.close()

    watchlist = {entry.code for entry in load_watchlist(settings.meta_dir)}
    items = [_to_item(rule, watchlist, last_dates.get(rule.id)) for rule in rules]
    return {
        "items": items,
        "total": len(items),
        "enabledCount": sum(1 for item in items if item["enabled"]),
    }


def create_rule(
    settings: Settings,
    *,
    type: str,
    name: str,
    scope: str,
    scope_code: str | None,
    window: int,
    threshold: float | None,
) -> dict:
    """新建规则：先建为停用态，回放补齐历史状态后才启用。

    回放失败时规则留在停用态（不会参与求值），用户可在列表里重试启用——
    这比「建好了但状态错的规则在跑」安全得多。
    """
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        rule = rule_store.create_rule(
            conn,
            type=type,
            name=name,
            scope=scope,
            scope_code=scope_code,
            window=window,
            threshold=threshold,
            enabled=False,
            timezone=settings.timezone,
        )
    finally:
        conn.close()

    replay = rule_eval.replay_rule(settings, rule.id)
    enabled = _enable(settings, rule.id)
    return {**_to_item(enabled, _watchlist(settings), None), "replay": replay}


def update_rule(
    settings: Settings,
    rule_id: int,
    *,
    name: str,
    window: int,
    threshold: float | None,
) -> dict:
    """修改名称与判定参数。参数变化时先按旧口径收尾，新参数从次日求值起算。"""
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        existing = rule_store.get_rule(conn, rule_id)
        if existing is None:
            raise LookupError(f"规则不存在：{rule_id}")

        changed = existing.window != int(window) or existing.threshold != threshold
        closed = (
            rule_store.close_states(
                conn, rule_id, reason="rule_changed", timezone=settings.timezone
            )
            if changed
            else []
        )
        rule = rule_store.update_rule(
            conn,
            rule_id,
            name=name,
            window=window,
            threshold=threshold,
            timezone=settings.timezone,
        )
        last_dates = rule_store.last_enter_dates(conn)
    finally:
        conn.close()

    assert rule is not None
    return {
        **_to_item(rule, _watchlist(settings), last_dates.get(rule.id)),
        "closedCodes": closed,
    }


def set_enabled(settings: Settings, rule_id: int, enabled: bool) -> dict:
    """停用（收尾当前触发态）或启用（先回放补历史）。重复调用幂等。"""
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        existing = rule_store.get_rule(conn, rule_id)
        if existing is None:
            raise LookupError(f"规则不存在：{rule_id}")
        already = existing.enabled
    finally:
        conn.close()

    if already == enabled:
        return {"rule": existing.as_dict(), "changed": False, "replay": None}

    if not enabled:
        conn = connect(settings.meta_dir, settings.timezone)
        try:
            closed = rule_store.close_states(
                conn, rule_id, reason="rule_disabled", timezone=settings.timezone
            )
            rule = rule_store.set_enabled(conn, rule_id, False)
        finally:
            conn.close()
        assert rule is not None
        return {
            "rule": rule.as_dict(),
            "changed": True,
            "closedCodes": closed,
            "replay": None,
        }

    # 启用：先补历史（停用期间可能本该触发），再把规则放回求值范围
    replay = rule_eval.replay_rule(settings, rule_id, until=now_iso(settings.timezone)[:10])
    rule = _enable(settings, rule_id)
    return {"rule": rule.as_dict(), "changed": True, "replay": replay}


def _enable(settings: Settings, rule_id: int) -> Rule:
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        rule = rule_store.set_enabled(conn, rule_id, True)
    finally:
        conn.close()
    if rule is None:  # pragma: no cover - 回放与启用之间规则被删才会走到
        raise LookupError(f"规则不存在：{rule_id}")
    return rule


def _watchlist(settings: Settings) -> set[str]:
    return {entry.code for entry in load_watchlist(settings.meta_dir)}


def _to_item(rule: Rule, watchlist: set[str], last_triggered: str | None) -> dict:
    return {
        **rule.as_dict(),
        "typeLabel": RULE_TYPE_LABELS.get(rule.type, rule.type),
        "scopeLabel": SCOPE_LABELS.get(rule.scope, rule.scope),
        # 「覆盖多少只标的」在新建后立刻要能看到（06 票验收标准第 6 条）
        "scopeCount": 1 if rule.scope == "single" else len(watchlist),
        "lastTriggeredAt": last_triggered,
    }


def validate_scope_change(scope: str | None) -> None:
    """标的范围不可原地修改：换范围会改变历史事件的归属，只能新建一条规则。"""
    if scope is not None:
        raise RuleValidationError("标的范围不可修改，如需换范围请新建规则")
