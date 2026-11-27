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
# 规则类型的分类口径只在这里定义一次，校验与求值都从这里取
THRESHOLD_RULE_TYPES = ("oversold", "volume_surge", "volume_shrink")
MA_RULE_TYPES = ("ma_cross",)
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
    -- 人工收尾（停用、改参数）的 exit 可能与当日那条 enter 同为一天，
    -- 因此唯一键包含 event；单次求值仍只产出一条事件（ADR 0007 修订说明）
    UNIQUE (code, rule_id, trade_date, event)
);

CREATE INDEX IF NOT EXISTS idx_event_code_rule
    ON rule_state_event (code, rule_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_event_alert_list
    ON rule_state_event (event, replayed, trade_date DESC);

-- 自选清单：用户数据，全库唯一一份。顺序靠 sort_order——added_at 只到秒，
-- 同一秒加入两只标的时它区分不出先后（2026-11-27 从 watchlist.json 迁入）
CREATE TABLE IF NOT EXISTS watchlist (
    code       TEXT    PRIMARY KEY,
    name       TEXT    NOT NULL DEFAULT '',
    kind       TEXT    NOT NULL DEFAULT 'stock' CHECK (kind IN ('stock', 'index')),
    added_at   TEXT    NOT NULL,
    sort_order INTEGER NOT NULL
);

-- 通知配置：单行（id = 1）。运行时由设置页修改，因此不放 config.toml（ADR 0009）
CREATE TABLE IF NOT EXISTS notification_config (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    ntfy_server   TEXT    NOT NULL DEFAULT 'https://ntfy.sh',
    ntfy_topic    TEXT,
    ntfy_token    TEXT,
    email_to      TEXT,
    smtp_host     TEXT,
    smtp_port     INTEGER,
    smtp_user     TEXT,
    smtp_password TEXT,
    smtp_starttls INTEGER NOT NULL DEFAULT 1,
    daily_limit   INTEGER NOT NULL DEFAULT 50,
    limit_enabled INTEGER NOT NULL DEFAULT 1,
    updated_at    TEXT    NOT NULL
);

-- 投递记录：每次尝试一行。event_id 为空表示设置页的测试通知，不占每日额度
CREATE TABLE IF NOT EXISTS notification_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     INTEGER REFERENCES rule_state_event(id),
    trade_date   TEXT    NOT NULL,
    channel      TEXT,
    result       TEXT    NOT NULL CHECK (result IN ('ok', 'fallback', 'failed')),
    detail       TEXT,
    attempted_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notify_log_date
    ON notification_log (trade_date, event_id);

-- 日报：每个交易日一份快照。已投递的内容不再改写（09 票验收标准）
CREATE TABLE IF NOT EXISTS daily_report (
    trade_date   TEXT PRIMARY KEY,
    content      TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL,
    pushed_at    TEXT,
    push_channel TEXT
);

-- 收盘流水线的运行记录（10 号票）。同一天可以重跑，因此不设唯一键。
CREATE TABLE IF NOT EXISTS pipeline_run (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date   TEXT    NOT NULL,
    trigger_kind TEXT    NOT NULL CHECK (trigger_kind IN ('scheduled', 'manual', 'catchup')),
    status       TEXT    NOT NULL CHECK (status IN ('running', 'ok', 'failed', 'skipped')),
    started_at   TEXT    NOT NULL,
    finished_at  TEXT,
    error        TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_run_date
    ON pipeline_run (trade_date, started_at DESC);

-- 单次运行的各阶段结果：失败在哪一步、各自耗时多少
CREATE TABLE IF NOT EXISTS pipeline_stage (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     INTEGER NOT NULL REFERENCES pipeline_run(id),
    stage      TEXT    NOT NULL,
    status     TEXT    NOT NULL CHECK (status IN ('ok', 'skipped', 'failed')),
    elapsed_ms INTEGER NOT NULL,
    detail     TEXT,
    error      TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_stage_run
    ON pipeline_stage (run_id);

-- 增量游标：最后一个「整条流水线成功」的交易日。缺口由它与今天之间的日期推出。
CREATE TABLE IF NOT EXISTS pipeline_cursor (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    last_success_date TEXT,
    updated_at        TEXT    NOT NULL
);
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
