# -*- coding: utf-8 -*-
"""通知配置与投递记录的读写（08 号票，ADR 0009）。

配置是用户数据而不是部署参数，因此落在 `meta.db`，由设置端点读写；
密码类字段只在库里保存明文，读取接口负责脱敏。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.storage.meta_db import now_iso

DEFAULT_NTFY_SERVER = "https://ntfy.sh"
DEFAULT_DAILY_LIMIT = 50

# 结果口径：ok 首选通道直接成功；fallback 首选失败后由备用通道送出；failed 全部失败
RESULT_OK = "ok"
RESULT_FALLBACK = "fallback"
RESULT_FAILED = "failed"


@dataclass(frozen=True)
class NotificationConfig:
    ntfy_server: str
    ntfy_topic: str | None
    ntfy_token: str | None
    email_to: str | None
    smtp_host: str | None
    smtp_port: int | None
    smtp_user: str | None
    smtp_password: str | None
    smtp_starttls: bool
    daily_limit: int
    limit_enabled: bool
    updated_at: str | None

    @property
    def ntfy_ready(self) -> bool:
        return bool(self.ntfy_topic)

    @property
    def email_ready(self) -> bool:
        return bool(self.smtp_host and self.email_to)

    @property
    def configured(self) -> bool:
        """至少有一个可用通道。两者都没配时求值只落库、不投递。"""
        return self.ntfy_ready or self.email_ready

    def effective_limit(self) -> int | None:
        """当日允许尝试投递的条数上限；关闭上限时返回 None。"""
        return self.daily_limit if self.limit_enabled else None


def load_config(conn: sqlite3.Connection) -> NotificationConfig:
    """读取配置；从未保存过时返回默认值（不写库）。"""
    row = conn.execute("SELECT * FROM notification_config WHERE id = 1").fetchone()
    if row is None:
        return NotificationConfig(
            ntfy_server=DEFAULT_NTFY_SERVER,
            ntfy_topic=None,
            ntfy_token=None,
            email_to=None,
            smtp_host=None,
            smtp_port=None,
            smtp_user=None,
            smtp_password=None,
            smtp_starttls=True,
            daily_limit=DEFAULT_DAILY_LIMIT,
            limit_enabled=True,
            updated_at=None,
        )
    return NotificationConfig(
        ntfy_server=row["ntfy_server"],
        ntfy_topic=row["ntfy_topic"],
        ntfy_token=row["ntfy_token"],
        email_to=row["email_to"],
        smtp_host=row["smtp_host"],
        smtp_port=None if row["smtp_port"] is None else int(row["smtp_port"]),
        smtp_user=row["smtp_user"],
        smtp_password=row["smtp_password"],
        smtp_starttls=bool(row["smtp_starttls"]),
        daily_limit=int(row["daily_limit"]),
        limit_enabled=bool(row["limit_enabled"]),
        updated_at=row["updated_at"],
    )


def save_config(
    conn: sqlite3.Connection,
    updates: dict[str, object],
    *,
    timezone: str = "Asia/Shanghai",
) -> NotificationConfig:
    """按传入字段覆盖保存；未传的字段保持原值。"""
    current = load_config(conn)
    merged = {
        "ntfy_server": updates.get("ntfy_server", current.ntfy_server),
        "ntfy_topic": updates.get("ntfy_topic", current.ntfy_topic),
        "ntfy_token": updates.get("ntfy_token", current.ntfy_token),
        "email_to": updates.get("email_to", current.email_to),
        "smtp_host": updates.get("smtp_host", current.smtp_host),
        "smtp_port": updates.get("smtp_port", current.smtp_port),
        "smtp_user": updates.get("smtp_user", current.smtp_user),
        "smtp_password": updates.get("smtp_password", current.smtp_password),
        "smtp_starttls": int(
            bool(updates.get("smtp_starttls", current.smtp_starttls))
        ),
        "daily_limit": updates.get("daily_limit", current.daily_limit),
        "limit_enabled": int(bool(updates.get("limit_enabled", current.limit_enabled))),
    }
    conn.execute(
        """
        INSERT INTO notification_config
            (id, ntfy_server, ntfy_topic, ntfy_token, email_to, smtp_host, smtp_port,
             smtp_user, smtp_password, smtp_starttls, daily_limit, limit_enabled, updated_at)
        VALUES (1, :ntfy_server, :ntfy_topic, :ntfy_token, :email_to, :smtp_host, :smtp_port,
                :smtp_user, :smtp_password, :smtp_starttls, :daily_limit, :limit_enabled, :updated_at)
        ON CONFLICT (id) DO UPDATE SET
            ntfy_server   = excluded.ntfy_server,
            ntfy_topic    = excluded.ntfy_topic,
            ntfy_token    = excluded.ntfy_token,
            email_to      = excluded.email_to,
            smtp_host     = excluded.smtp_host,
            smtp_port     = excluded.smtp_port,
            smtp_user     = excluded.smtp_user,
            smtp_password = excluded.smtp_password,
            smtp_starttls = excluded.smtp_starttls,
            daily_limit   = excluded.daily_limit,
            limit_enabled = excluded.limit_enabled,
            updated_at    = excluded.updated_at
        """,
        {**merged, "updated_at": now_iso(timezone)},
    )
    return load_config(conn)


def attempted_ids(conn: sqlite3.Connection, trade_date: str) -> set[int]:
    """该交易日已经尝试投递过的预警 id（不含设置页的测试通知）。"""
    rows = conn.execute(
        """
        SELECT DISTINCT event_id FROM notification_log
        WHERE trade_date = ? AND event_id IS NOT NULL
        """,
        (trade_date,),
    ).fetchall()
    return {int(row[0]) for row in rows}


def latest_attempt_date(conn: sqlite3.Connection) -> str | None:
    """最近一次投递对应的交易日。上限按交易日计，展示用量也要用同一个日期。"""
    row = conn.execute("SELECT MAX(trade_date) FROM notification_log").fetchone()
    return None if row is None or row[0] in (None, "") else str(row[0])


def log_attempt(
    conn: sqlite3.Connection,
    *,
    event_id: int | None,
    trade_date: str,
    channel: str | None,
    result: str,
    detail: str | None = None,
    timezone: str = "Asia/Shanghai",
) -> None:
    conn.execute(
        """
        INSERT INTO notification_log (event_id, trade_date, channel, result, detail, attempted_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (event_id, trade_date, channel, result, detail, now_iso(timezone)),
    )


def list_logs(
    conn: sqlite3.Connection,
    *,
    trade_date: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[sqlite3.Row], int]:
    """投递记录，按尝试时间倒序分页。"""
    where = ""
    params: list[object] = []
    if trade_date:
        where = " WHERE l.trade_date = ?"
        params.append(trade_date)

    base = """
        FROM notification_log l
        LEFT JOIN rule_state_event e ON e.id = l.event_id
        LEFT JOIN alert_rule r ON r.id = e.rule_id
    """
    total = conn.execute("SELECT COUNT(*)" + base + where, params).fetchone()[0]
    rows = conn.execute(
        "SELECT l.*, e.code AS code, r.name AS rule_name" + base + where
        + " ORDER BY l.id DESC LIMIT ? OFFSET ?",
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    return rows, int(total)
