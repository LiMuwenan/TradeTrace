# -*- coding: utf-8 -*-
"""收盘流水线的运行记录与增量游标（10 号票）。

游标只记录「整条流水线都成功」的最后一个交易日；缺口就是它与今天之间那些
没有成功记录的日期。失败不需要单独建缺口表——`pipeline_run` 里 status='failed' 的行就是。
"""
from __future__ import annotations

import sqlite3

from app.storage.meta_db import now_iso


def start_run(
    conn: sqlite3.Connection,
    trade_date: str,
    trigger_kind: str,
    *,
    timezone: str = "Asia/Shanghai",
) -> int:
    cursor = conn.execute(
        "INSERT INTO pipeline_run (trade_date, trigger_kind, status, started_at) VALUES (?, ?, 'running', ?)",
        (trade_date, trigger_kind, now_iso(timezone)),
    )
    return int(cursor.lastrowid)


def add_stage(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    stage: str,
    status: str,
    elapsed_ms: int,
    detail: str | None = None,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO pipeline_stage (run_id, stage, status, elapsed_ms, detail, error)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, stage, status, elapsed_ms, detail, error),
    )


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    *,
    error: str | None = None,
    timezone: str = "Asia/Shanghai",
) -> None:
    conn.execute(
        "UPDATE pipeline_run SET status = ?, finished_at = ?, error = ? WHERE id = ?",
        (status, now_iso(timezone), error, run_id),
    )


def get_run(conn: sqlite3.Connection, run_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM pipeline_run WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    return _to_run(row, _stages_for(conn, [run_id]).get(run_id, []))


def list_runs(
    conn: sqlite3.Connection, *, page: int = 1, page_size: int = 20, trade_date: str | None = None
) -> tuple[list[dict], int]:
    where, params = "", []
    if trade_date:
        where, params = " WHERE trade_date = ?", [trade_date]
    total = int(
        conn.execute("SELECT COUNT(*) FROM pipeline_run" + where, params).fetchone()[0]
    )
    rows = conn.execute(
        "SELECT * FROM pipeline_run"
        + where
        + " ORDER BY started_at DESC, id DESC LIMIT ? OFFSET ?",
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    stages = _stages_for(conn, [int(row["id"]) for row in rows])
    return [_to_run(row, stages.get(int(row["id"]), [])) for row in rows], total


def get_cursor(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT last_success_date FROM pipeline_cursor WHERE id = 1"
    ).fetchone()
    return None if row is None else row["last_success_date"]


def advance_cursor(
    conn: sqlite3.Connection, trade_date: str, *, timezone: str = "Asia/Shanghai"
) -> None:
    """只前进不后退：补跑历史日期不能把游标拉回去。"""
    current = get_cursor(conn)
    if current is not None and current >= trade_date:
        return
    conn.execute(
        """
        INSERT INTO pipeline_cursor (id, last_success_date, updated_at) VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE
            SET last_success_date = excluded.last_success_date, updated_at = excluded.updated_at
        """,
        (trade_date, now_iso(timezone)),
    )


def failed_dates(conn: sqlite3.Connection, *, since: str, until: str) -> list[str]:
    """在 [since, until] 内失败的交易日（去重、升序），供次日补跑。"""
    rows = conn.execute(
        """
        SELECT DISTINCT trade_date FROM pipeline_run
        WHERE status = 'failed' AND trade_date BETWEEN ? AND ?
        ORDER BY trade_date
        """,
        (since, until),
    ).fetchall()
    return [row["trade_date"] for row in rows]


def _stages_for(
    conn: sqlite3.Connection, run_ids: list[int]
) -> dict[int, list[dict]]:
    if not run_ids:
        return {}
    placeholders = ",".join("?" for _ in run_ids)
    rows = conn.execute(
        f"SELECT * FROM pipeline_stage WHERE run_id IN ({placeholders}) ORDER BY id",
        run_ids,
    ).fetchall()
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(int(row["run_id"]), []).append(
            {
                "stage": row["stage"],
                "status": row["status"],
                "elapsedMs": int(row["elapsed_ms"]),
                "detail": row["detail"],
                "error": row["error"],
            }
        )
    return grouped


def _to_run(row: sqlite3.Row, stages: list[dict]) -> dict:
    return {
        "id": int(row["id"]),
        "tradeDate": row["trade_date"],
        "triggerKind": row["trigger_kind"],
        "status": row["status"],
        "startedAt": row["started_at"],
        "finishedAt": row["finished_at"],
        "error": row["error"],
        "stages": stages,
    }
