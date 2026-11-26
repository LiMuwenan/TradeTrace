# -*- coding: utf-8 -*-
"""通知设置：配置读写、测试通知、投递记录（08 号票）。

设置在库里（ADR 0009），所以这里既不是配置加载也不是纯查询，而是「用户可改的配置」。
密码类字段读取时不回显，写入时缺省表示不修改、空串表示清空。
"""
from __future__ import annotations

from app.config import Settings
from app.services.notify import AlertNotifier, build_test_alert
from app.storage import notify_store
from app.storage.meta_db import connect, now_iso

MAX_DAILY_LIMIT = 1000

# 前端 camelCase → 库字段
FIELD_MAP = {
    "ntfyServer": "ntfy_server",
    "ntfyTopic": "ntfy_topic",
    "ntfyToken": "ntfy_token",
    "emailTo": "email_to",
    "smtpHost": "smtp_host",
    "smtpPort": "smtp_port",
    "smtpUser": "smtp_user",
    "smtpPassword": "smtp_password",
    "smtpStarttls": "smtp_starttls",
    "dailyLimit": "daily_limit",
    "limitEnabled": "limit_enabled",
}

STRING_FIELDS = ("ntfy_server", "ntfy_topic", "ntfy_token", "email_to", "smtp_host", "smtp_user", "smtp_password")


class NotifyConfigError(ValueError):
    """配置非法，消息面向用户，可直接展示。"""


def read_config(settings: Settings) -> dict:
    """当前配置（凭据脱敏）+ 当日用量。"""
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        config = notify_store.load_config(conn)
        usage = _usage(conn, settings, config)
    finally:
        conn.close()
    return _public(config, usage)


def update_config(settings: Settings, updates: dict) -> dict:
    """保存配置。`updates` 的键是 camelCase，只处理传入的字段。"""
    normalized = _normalize_updates(updates)
    _validate(normalized)

    conn = connect(settings.meta_dir, settings.timezone)
    try:
        config = notify_store.save_config(conn, normalized, timezone=settings.timezone)
        usage = _usage(conn, settings, config)
    finally:
        conn.close()
    return _public(config, usage)


def test_notification(settings: Settings) -> dict:
    """发一条测试通知，返回实际走的通道与错误摘要。不占每日额度。"""
    notifier = AlertNotifier(settings)
    if not notifier.configured:
        return {"ok": False, "channel": None, "error": "尚未配置任何通知通道"}
    outcome = notifier.send_test(build_test_alert(settings))
    return {"ok": outcome.ok, "channel": outcome.channel, "error": outcome.error}


def read_logs(
    settings: Settings, *, trade_date: str | None = None, page: int = 1, page_size: int = 20
) -> dict:
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        rows, total = notify_store.list_logs(
            conn, trade_date=trade_date, page=page, page_size=page_size
        )
    finally:
        conn.close()
    items = [
        {
            "id": int(row["id"]),
            "eventId": None if row["event_id"] is None else int(row["event_id"]),
            "code": row["code"],
            "ruleName": row["rule_name"],
            "tradeDate": row["trade_date"],
            "channel": row["channel"],
            "result": row["result"],
            "detail": row["detail"],
            "attemptedAt": row["attempted_at"],
        }
        for row in rows
    ]
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


def _normalize_updates(updates: dict) -> dict:
    """camelCase → 库字段。字符串空串表示清空，数字与布尔缺省表示不修改。"""
    normalized: dict[str, object] = {}
    for camel, value in updates.items():
        field = FIELD_MAP.get(camel)
        if field is None:
            continue
        if field in STRING_FIELDS:
            text = "" if value is None else str(value).strip()
            if field == "ntfy_server" and not text:
                # 服务地址没有「清空」语义，留空即恢复默认，避免落 None 后拼 URL 报错
                normalized[field] = notify_store.DEFAULT_NTFY_SERVER
                continue
            normalized[field] = text or None
        elif value is not None:
            normalized[field] = value
    return normalized


def _validate(updates: dict) -> None:
    server = updates.get("ntfy_server")
    if server is not None and not str(server).startswith(("http://", "https://")):
        raise NotifyConfigError("ntfy 服务地址需以 http:// 或 https:// 开头")

    email_to = updates.get("email_to")
    if email_to is not None and "@" not in str(email_to):
        raise NotifyConfigError(f"收件邮箱不合法：{email_to}")

    port = updates.get("smtp_port")
    if port is not None and not 1 <= int(port) <= 65535:
        raise NotifyConfigError(f"SMTP 端口非法：{port}，应在 1-65535 之间")

    limit = updates.get("daily_limit")
    if limit is not None and not 1 <= int(limit) <= MAX_DAILY_LIMIT:
        raise NotifyConfigError(f"每日上限应在 1-{MAX_DAILY_LIMIT} 之间，当前为 {limit}")


def _usage(conn, settings: Settings, config: notify_store.NotificationConfig) -> dict:
    """当日用量。上限按交易日计，所以展示的也必须是交易日而不是自然日。"""
    trade_date = notify_store.latest_attempt_date(conn) or now_iso(settings.timezone)[:10]
    return {
        "date": trade_date,
        "attempted": len(notify_store.attempted_ids(conn, trade_date)),
        "limit": config.effective_limit(),
    }


def _public(config: notify_store.NotificationConfig, usage: dict) -> dict:
    return {
        "ntfyServer": config.ntfy_server,
        "ntfyTopic": config.ntfy_topic,
        "ntfyTokenConfigured": bool(config.ntfy_token),
        "emailTo": config.email_to,
        "smtpHost": config.smtp_host,
        "smtpPort": config.smtp_port,
        "smtpUser": config.smtp_user,
        "smtpPasswordConfigured": bool(config.smtp_password),
        "smtpStarttls": config.smtp_starttls,
        "dailyLimit": config.daily_limit,
        "limitEnabled": config.limit_enabled,
        "configured": config.configured,
        "ntfyReady": config.ntfy_ready,
        "emailReady": config.email_ready,
        "updatedAt": config.updated_at,
        "usage": usage,
    }
