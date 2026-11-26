# -*- coding: utf-8 -*-
"""规则定义与触发态变更记录的读写。

规则参数校验集中在这里，06 的表单与配置文件种子共用同一套口径。
"""
from __future__ import annotations

import sqlite3
import tomllib
from pathlib import Path

from app.storage.meta_db import (
    RULE_TYPES,
    SCOPES,
    THRESHOLD_RULE_TYPES,
    Rule,
    RuleValidationError,
    _row_to_rule,
    now_iso,
)
from app.storage.schema import IngestError, normalize_code


def validate_rule(
    *,
    type: str,
    scope: str,
    scope_code: str | None,
    window: int,
    threshold: float | None,
) -> tuple[str, str | None, int, float | None]:
    """校验并归一化规则参数，返回可直接入库的四元组。"""
    if type not in RULE_TYPES:
        raise RuleValidationError(f"未知的规则类型：{type}，可选 {'/'.join(RULE_TYPES)}")
    if scope not in SCOPES:
        raise RuleValidationError(f"未知的标的范围：{scope}，可选 {'/'.join(SCOPES)}")

    if scope == "single":
        if not scope_code:
            raise RuleValidationError("标的范围为「指定单只」时必须给出标的代码")
        try:
            scope_code = normalize_code(scope_code)
        except IngestError as exc:
            raise RuleValidationError(str(exc)) from exc
    else:
        scope_code = None

    try:
        window = int(window)
    except (TypeError, ValueError) as exc:
        raise RuleValidationError(f"时间窗必须是整数：{window!r}") from exc
    if window < 2:
        raise RuleValidationError(f"时间窗不得小于 2，当前为 {window}")

    if type in THRESHOLD_RULE_TYPES:
        if threshold is None:
            raise RuleValidationError(f"规则类型 {type} 必须给出阈值")
        threshold = float(threshold)
        if type == "oversold":
            if not 0 < threshold <= 100:
                raise RuleValidationError(f"超跌阈值应在 (0, 100] 区间内（百分数），当前为 {threshold}")
        elif threshold <= 0:
            raise RuleValidationError(f"量比阈值必须大于 0，当前为 {threshold}")
    else:
        threshold = None

    return type, scope_code, window, threshold


def create_rule(
    conn: sqlite3.Connection,
    *,
    type: str,
    name: str,
    scope: str = "watchlist",
    scope_code: str | None = None,
    window: int,
    threshold: float | None = None,
    enabled: bool = True,
    timezone: str = "Asia/Shanghai",
) -> Rule:
    type, scope_code, window, threshold = validate_rule(
        type=type, scope=scope, scope_code=scope_code, window=window, threshold=threshold
    )
    name = (name or "").strip()
    if not name:
        raise RuleValidationError("规则名称不能为空")

    cursor = conn.execute(
        """
        INSERT INTO alert_rule (type, name, scope, scope_code, window, threshold, enabled, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (type, name, scope, scope_code, window, threshold, 1 if enabled else 0, now_iso(timezone)),
    )
    rule = get_rule(conn, int(cursor.lastrowid))
    assert rule is not None
    return rule


def get_rule(conn: sqlite3.Connection, rule_id: int) -> Rule | None:
    row = conn.execute("SELECT * FROM alert_rule WHERE id = ?", (rule_id,)).fetchone()
    return None if row is None else _row_to_rule(row)


def list_rules(conn: sqlite3.Connection, *, enabled_only: bool = False) -> list[Rule]:
    sql = "SELECT * FROM alert_rule"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY id"
    return [_row_to_rule(row) for row in conn.execute(sql).fetchall()]


def close_states(
    conn: sqlite3.Connection, rule_id: int, *, reason: str, timezone: str = "Asia/Shanghai"
) -> list[str]:
    """把某规则当前所有处于触发态的标的收尾：各写一条带原因的 exit（ADR 0007 第 7 条）。

    规则改参数或停用时由 06 调用，避免旧口径的「满足」状态被新参数继续沿用。
    返回被收尾的标的代码。
    """
    rows = conn.execute(
        """
        SELECT code FROM rule_state_event
        WHERE rule_id = ? AND event = 'enter'
          AND NOT EXISTS (
              SELECT 1 FROM rule_state_event newer
              WHERE newer.code = rule_state_event.code
                AND newer.rule_id = rule_state_event.rule_id
                AND (newer.trade_date, newer.id) > (rule_state_event.trade_date, rule_state_event.id)
          )
        """,
        (rule_id,),
    ).fetchall()
    closed: list[str] = []
    for row in rows:
        code = row["code"]
        if record_event(
            conn,
            code=code,
            rule_id=rule_id,
            trade_date=last_event(conn, code, rule_id)["trade_date"],
            event="exit",
            reason=reason,
            timezone=timezone,
        ):
            closed.append(code)
    return closed


def import_seed_rules(conn: sqlite3.Connection, path: Path | str, timezone: str = "Asia/Shanghai") -> list[Rule]:
    """从 TOML 导入种子规则（06 上线前的调试后门，见 05 票备注）。"""
    path = Path(path)
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    created: list[Rule] = []
    for item in raw.get("rules") or []:
        created.append(
            create_rule(
                conn,
                type=str(item.get("type", "")),
                name=str(item.get("name", "")),
                scope=str(item.get("scope", "watchlist")),
                scope_code=item.get("scope_code") or item.get("scopeCode"),
                window=item.get("window", 0),
                threshold=item.get("threshold"),
                enabled=bool(item.get("enabled", True)),
                timezone=timezone,
            )
        )
    return created


# --- 触发态变更记录 -------------------------------------------------------


def last_event(conn: sqlite3.Connection, code: str, rule_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM rule_state_event
        WHERE code = ? AND rule_id = ?
        ORDER BY trade_date DESC, id DESC
        LIMIT 1
        """,
        (code, rule_id),
    ).fetchone()


def current_state(conn: sqlite3.Connection, code: str, rule_id: int) -> str | None:
    """当前触发态：最后一条事件是 enter 则为 'enter'，否则 'exit'／无记录为 None。"""
    row = last_event(conn, code, rule_id)
    return None if row is None else row["event"]


def record_event(
    conn: sqlite3.Connection,
    *,
    code: str,
    rule_id: int,
    trade_date: str,
    event: str,
    value: float | None = None,
    threshold: float | None = None,
    price: float | None = None,
    reason: str | None = None,
    replayed: bool = False,
    timezone: str = "Asia/Shanghai",
) -> bool:
    """写入一条变更记录。唯一键冲突时忽略，返回是否真的插入（幂等）。"""
    if event not in ("enter", "exit"):
        raise ValueError(f"非法的事件类型：{event}")
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO rule_state_event
            (code, rule_id, trade_date, event, value, threshold, price, reason, replayed, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            code,
            rule_id,
            trade_date,
            event,
            value,
            threshold,
            price,
            reason,
            1 if replayed else 0,
            now_iso(timezone),
        ),
    )
    return cursor.rowcount == 1


def pending_alerts(conn: sqlite3.Connection, trade_date: str | None = None) -> list[sqlite3.Row]:
    """待投递的预警：未推送过、非回放产生的 enter 记录。"""
    sql = """
        SELECT e.*, r.type AS rule_type, r.name AS rule_name, r.window AS rule_window
        FROM rule_state_event e
        JOIN alert_rule r ON r.id = e.rule_id
        WHERE e.event = 'enter'
          AND e.replayed = 0
          AND e.pushed_at IS NULL
    """
    params: tuple[object, ...] = ()
    if trade_date is not None:
        sql += " AND e.trade_date = ?"
        params = (trade_date,)
    sql += " ORDER BY e.trade_date, e.id"
    return conn.execute(sql, params).fetchall()


def mark_pushed(
    conn: sqlite3.Connection,
    event_id: int,
    *,
    channel: str,
    timezone: str = "Asia/Shanghai",
) -> None:
    conn.execute(
        "UPDATE rule_state_event SET pushed_at = ?, push_channel = ? WHERE id = ?",
        (now_iso(timezone), channel, event_id),
    )


def history(conn: sqlite3.Connection, rule_id: int, code: str) -> list[sqlite3.Row]:
    """某标的某规则的触发历史：按交易日升序，含进入与解除。"""
    return conn.execute(
        """
        SELECT * FROM rule_state_event
        WHERE rule_id = ? AND code = ?
        ORDER BY trade_date, id
        """,
        (rule_id, code),
    ).fetchall()


# --- 预警阅读（07 号票）----------------------------------------------------
#
# 预警就是 event='enter' 且 replayed=0 的行；已读就是这行的 read_at。
# 本组查询只服务 Web 列表与详情，不改事件流本身的写入口径。

_ALERT_SELECT = """
    SELECT e.*, r.type AS rule_type, r.name AS rule_name, r.window AS rule_window
    FROM rule_state_event e
    JOIN alert_rule r ON r.id = e.rule_id
"""


def list_alerts(
    conn: sqlite3.Connection,
    *,
    read: bool | None = None,
    code: str | None = None,
    rule_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[sqlite3.Row], int]:
    """预警列表与总数：按交易日倒序分页，默认排除静默回放产生的进入记录。"""
    where = ["e.event = 'enter'", "e.replayed = 0"]
    params: list[object] = []
    if read is True:
        where.append("e.read_at IS NOT NULL")
    elif read is False:
        where.append("e.read_at IS NULL")
    if code:
        where.append("e.code = ?")
        params.append(code)
    if rule_type:
        where.append("r.type = ?")
        params.append(rule_type)

    clause = " WHERE " + " AND ".join(where)
    total = conn.execute(
        "SELECT COUNT(*) FROM rule_state_event e JOIN alert_rule r ON r.id = e.rule_id" + clause,
        params,
    ).fetchone()[0]
    rows = conn.execute(
        _ALERT_SELECT + clause + " ORDER BY e.trade_date DESC, e.id DESC LIMIT ? OFFSET ?",
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    return rows, int(total)


def unread_alert_count(conn: sqlite3.Connection) -> int:
    """未读预警数，口径与列表一致（排除回放）。"""
    return int(
        conn.execute(
            """
            SELECT COUNT(*) FROM rule_state_event
            WHERE event = 'enter' AND replayed = 0 AND read_at IS NULL
            """
        ).fetchone()[0]
    )


def get_alert(conn: sqlite3.Connection, alert_id: int) -> sqlite3.Row | None:
    """单条预警（含所属规则的类型与名称）。解除记录与回放记录都不是预警，查不到。"""
    return conn.execute(
        _ALERT_SELECT + " WHERE e.id = ? AND e.event = 'enter' AND e.replayed = 0",
        (alert_id,),
    ).fetchone()


def set_alert_read(
    conn: sqlite3.Connection,
    alert_id: int,
    read: bool,
    *,
    timezone: str = "Asia/Shanghai",
) -> bool:
    """切换单条已读/未读，返回是否命中一条预警。回放记录不参与已读状态。"""
    cursor = conn.execute(
        """
        UPDATE rule_state_event SET read_at = ?
        WHERE id = ? AND event = 'enter' AND replayed = 0
        """,
        (now_iso(timezone) if read else None, alert_id),
    )
    return cursor.rowcount == 1


def mark_all_alerts_read(conn: sqlite3.Connection, *, timezone: str = "Asia/Shanghai") -> int:
    """一键全部已读，返回受影响条数。"""
    cursor = conn.execute(
        """
        UPDATE rule_state_event SET read_at = ?
        WHERE event = 'enter' AND replayed = 0 AND read_at IS NULL
        """,
        (now_iso(timezone),),
    )
    return cursor.rowcount
