# -*- coding: utf-8 -*-
"""用户记录库 meta.db：规则定义与触发态变更记录的表结构与写入契约。"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DB_FILENAME = "meta.db"

RULE_TYPES = ("breakout", "oversold", "volume_surge", "volume_shrink", "ma_cross")
SCOPES = ("watchlist", "single")

SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_rule (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    scope       TEXT    NOT NULL,
    scope_code  TEXT,
    window      INTEGER NOT NULL,
    threshold   REAL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL
);

-- 触发态变更记录。预警就是 event='enter' 的行；触发态由最后一条事件推导，不落库。
CREATE TABLE IF NOT EXISTS rule_state_event (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT    NOT NULL,
    rule_id      INTEGER NOT NULL REFERENCES alert_rule(id),
    trade_date   TEXT    NOT NULL,
    event        TEXT    NOT NULL CHECK (event IN ('enter', 'exit')),
    value        REAL,
    threshold    REAL,
    price        REAL,
    reason       TEXT,
    replayed     INTEGER NOT NULL DEFAULT 0,
    pushed_at    TEXT,
    push_channel TEXT,
    read_at      TEXT,
    created_at   TEXT    NOT NULL,
    UNIQUE (code, rule_id, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_event_code_rule
    ON rule_state_event (code, rule_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_event_alert_list
    ON rule_state_event (event, replayed, trade_date DESC);
"""


class RuleValidationError(ValueError):
    """规则参数不合格，消息面向用户，可直接展示。"""


def db_path(meta_dir: Path | str) -> Path:
    return Path(meta_dir) / DB_FILENAME


def connect(meta_dir: Path | str, timezone: str = "Asia/Shanghai") -> sqlite3.Connection:
    """打开 meta.db 并确保表已建好。单文件、WAL、写操作串行。"""
    path = db_path(meta_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def now_iso(timezone: str = "Asia/Shanghai") -> str:
    return datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Rule:
    id: int
    type: str
    name: str
    scope: str
    scope_code: str | None
    window: int
    threshold: float | None
    enabled: bool
    created_at: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "scope": self.scope,
            "scopeCode": self.scope_code,
            "window": self.window,
            "threshold": self.threshold,
            "enabled": self.enabled,
            "createdAt": self.created_at,
        }


def _row_to_rule(row: sqlite3.Row) -> Rule:
    return Rule(
        id=int(row["id"]),
        type=row["type"],
        name=row["name"],
        scope=row["scope"],
        scope_code=row["scope_code"],
        window=int(row["window"]),
        threshold=None if row["threshold"] is None else float(row["threshold"]),
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
    )
