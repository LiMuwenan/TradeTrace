# -*- coding: utf-8 -*-
"""日报快照的读写（09 号票）。

一条纪律：**已投递的日报不再改写**。同一天重跑只允许更新还没投递的草稿，
否则「昨天晚上收到的那封邮件」与「今天在 Web 上看到的日报」会不是同一份内容。
"""
from __future__ import annotations

import json
import sqlite3

from app.storage.meta_db import now_iso


def get(conn: sqlite3.Connection, trade_date: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM daily_report WHERE trade_date = ?", (trade_date,)
    ).fetchone()


def save_draft(
    conn: sqlite3.Connection,
    trade_date: str,
    content: dict,
    *,
    timezone: str = "Asia/Shanghai",
) -> sqlite3.Row:
    """写入草稿；若该日已投递则原样返回，不改写。"""
    existing = get(conn, trade_date)
    if existing is not None and existing["pushed_at"]:
        return existing

    payload = json.dumps(content, ensure_ascii=False)
    now = now_iso(timezone)
    conn.execute(
        """
        INSERT INTO daily_report (trade_date, content, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(trade_date) DO UPDATE
            SET content = excluded.content, updated_at = excluded.updated_at
        """,
        (trade_date, payload, now, now),
    )
    row = get(conn, trade_date)
    assert row is not None
    return row


def mark_pushed(
    conn: sqlite3.Connection,
    trade_date: str,
    *,
    channel: str,
    timezone: str = "Asia/Shanghai",
) -> None:
    conn.execute(
        "UPDATE daily_report SET pushed_at = ?, push_channel = ? WHERE trade_date = ?",
        (now_iso(timezone), channel, trade_date),
    )


def list_reports(
    conn: sqlite3.Connection, *, page: int = 1, page_size: int = 20
) -> tuple[list[sqlite3.Row], int]:
    total = int(conn.execute("SELECT COUNT(*) FROM daily_report").fetchone()[0])
    rows = conn.execute(
        "SELECT * FROM daily_report ORDER BY trade_date DESC LIMIT ? OFFSET ?",
        (page_size, (page - 1) * page_size),
    ).fetchall()
    return rows, total


def latest_date(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(trade_date) FROM daily_report").fetchone()
    return None if row is None or row[0] is None else str(row[0])
