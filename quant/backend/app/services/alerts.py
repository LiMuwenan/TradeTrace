# -*- coding: utf-8 -*-
"""预警列表与阅读状态：把事件流中 `enter` 的行组装成 Web 可展示的预警（07 号票）。

口径（ADR 0007 + 07 票备注）：
- 预警就是 `event='enter'` 且 `replayed=0` 的行，不另建表；
- 已读就是这行的 `read_at`，单用户全局状态，不做多用户隔离；
- 详情只做读侧，不改变事件流的写入。
"""
from __future__ import annotations

from app.config import Settings
from app.storage import rule_store
from app.storage.meta_db import connect
from app.storage.schema import normalize_code
from app.storage.stock_names import StockNameCache

DISCLAIMER = "本内容仅为数据分析，不构成投资建议"
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def list_alerts(
    settings: Settings,
    stock_names: StockNameCache,
    *,
    read: bool | None = None,
    code: str | None = None,
    rule_type: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    """预警列表。`code` 非法时抛 IngestError，由路由转 400。"""
    normalized = normalize_code(code) if code else None
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        rows, total = rule_store.list_alerts(
            conn,
            read=read,
            code=normalized,
            rule_type=rule_type,
            page=page,
            page_size=page_size,
        )
        unread = rule_store.unread_alert_count(conn)
    finally:
        conn.close()

    names = stock_names.names()
    return {
        "items": [_to_item(row, names) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "unreadCount": unread,
    }


def alert_detail(
    settings: Settings, stock_names: StockNameCache, alert_id: int
) -> dict:
    """单条预警的触发快照与规则参数。不存在时抛 LookupError。"""
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        row = rule_store.get_alert(conn, alert_id)
        if row is None:
            raise LookupError(f"预警不存在：{alert_id}")
        rule = rule_store.get_rule(conn, int(row["rule_id"]))
    finally:
        conn.close()

    names = stock_names.names()
    return {
        "alert": _to_item(row, names),
        # 规则可能已被删除，此时详情只给快照值，不编造参数
        "rule": rule.as_dict() if rule is not None else None,
        "disclaimer": DISCLAIMER,
    }


def set_read(settings: Settings, alert_id: int, read: bool) -> dict:
    """切换单条已读/未读。返回新的状态；预警不存在时抛 LookupError。"""
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        if not rule_store.set_alert_read(conn, alert_id, read, timezone=settings.timezone):
            raise LookupError(f"预警不存在：{alert_id}")
        row = rule_store.get_alert(conn, alert_id)
        unread = rule_store.unread_alert_count(conn)
    finally:
        conn.close()
    assert row is not None
    return {"id": alert_id, "read": read, "readAt": row["read_at"], "unreadCount": unread}


def mark_all_read(settings: Settings) -> dict:
    """一键全部已读，返回受影响条数。"""
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        updated = rule_store.mark_all_alerts_read(conn, timezone=settings.timezone)
        unread = rule_store.unread_alert_count(conn)
    finally:
        conn.close()
    return {"updated": updated, "unreadCount": unread}


def _to_item(row, names: dict[str, str]) -> dict:
    return {
        "id": int(row["id"]),
        "code": row["code"],
        "name": names.get(row["code"], ""),
        "tradeDate": row["trade_date"],
        "ruleId": int(row["rule_id"]),
        "ruleType": row["rule_type"],
        "ruleName": row["rule_name"],
        "value": row["value"],
        "threshold": row["threshold"],
        "price": row["price"],
        "readAt": row["read_at"],
        "pushedAt": row["pushed_at"],
        "pushChannel": row["push_channel"],
        "createdAt": row["created_at"],
    }
