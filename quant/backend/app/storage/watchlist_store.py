# -*- coding: utf-8 -*-
"""自选清单的持久化：单用户、全局唯一一份，按添加顺序保存。

自选是用户数据，不能像 Parquet 那样从原始 CSV 重建，因此与规则、通知配置一起放在
`meta_dir/meta.db` 的 `watchlist` 表里（2026-11-27 从 `watchlist.json` 迁入，见 ADR 0011）。

两个设计点：

- **顺序用 `sort_order`**：`added_at` 只到秒，同一秒加入两只标的时它区分不出先后；
- **旧文件只导入一次**：表为空且 `watchlist.json` 存在时导入，导入成功把原文件改名成
  `watchlist.json.migrated`（不删）。改名是关键——否则用户清空自选后，旧文件会再次被导入。
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.storage.meta_db import connect

LEGACY_FILENAME = "watchlist.json"
MIGRATED_SUFFIX = ".migrated"

# 自选标的类型：股票与指数共用一份清单，靠这个字段区分行情来源
KIND_STOCK = "stock"
KIND_INDEX = "index"
KINDS = (KIND_STOCK, KIND_INDEX)

logger = logging.getLogger(__name__)


class WatchlistCorruptError(Exception):
    """旧版 `watchlist.json` 存在但无法解析。

    保留原文件并显式报错，避免用空清单覆盖用户数据。
    """


@dataclass(frozen=True)
class WatchlistEntry:
    code: str
    name: str
    added_at: str
    kind: str = KIND_STOCK

    def as_dict(self) -> dict:
        return {"code": self.code, "name": self.name, "addedAt": self.added_at, "kind": self.kind}


def load_watchlist(meta_dir: Path | str) -> list[WatchlistEntry]:
    """按添加顺序返回自选清单。"""
    conn = _open(meta_dir)
    try:
        return _read_all(conn)
    finally:
        conn.close()


def get_entry(meta_dir: Path | str, code: str) -> WatchlistEntry | None:
    conn = _open(meta_dir)
    try:
        return _read_one(conn, code)
    finally:
        conn.close()


def upsert_entry(meta_dir: Path | str, entry: WatchlistEntry) -> bool:
    """写入一条自选：已存在则更新名称与类型（顺序不动），返回是否新建。"""
    conn = _open(meta_dir)
    try:
        return _write(conn, entry)
    finally:
        conn.close()


def remove_entry(meta_dir: Path | str, code: str) -> bool:
    """删除一条自选，返回是否真的删掉了。"""
    conn = _open(meta_dir)
    try:
        cursor = conn.execute("DELETE FROM watchlist WHERE code = ?", (code,))
        return cursor.rowcount > 0
    finally:
        conn.close()


def save_watchlist(meta_dir: Path | str, entries: list[WatchlistEntry]) -> None:
    """整份替换。给迁移与测试用；日常增删走 `upsert_entry` / `remove_entry`。"""
    conn = _open(meta_dir)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("DELETE FROM watchlist")
            for order, entry in enumerate(entries, start=1):
                _insert(conn, entry, order)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def legacy_path(meta_dir: Path | str) -> Path:
    return Path(meta_dir) / LEGACY_FILENAME


def _open(meta_dir: Path | str) -> sqlite3.Connection:
    """开连接并确保旧文件已迁移——所有读写入口都必须先过这一步。"""
    conn = connect(meta_dir)
    try:
        _import_legacy(conn, meta_dir)
    except Exception:
        conn.close()
        raise
    return conn


def _read_all(conn: sqlite3.Connection) -> list[WatchlistEntry]:
    rows = conn.execute(
        "SELECT code, name, kind, added_at FROM watchlist ORDER BY sort_order, code"
    ).fetchall()
    return [_row_to_entry(row) for row in rows]


def _read_one(conn: sqlite3.Connection, code: str) -> WatchlistEntry | None:
    row = conn.execute(
        "SELECT code, name, kind, added_at FROM watchlist WHERE code = ?", (code,)
    ).fetchone()
    return None if row is None else _row_to_entry(row)


def _write(conn: sqlite3.Connection, entry: WatchlistEntry) -> bool:
    kind = entry.kind if entry.kind in KINDS else KIND_STOCK
    conn.execute("BEGIN IMMEDIATE")
    try:
        existing = conn.execute("SELECT 1 FROM watchlist WHERE code = ?", (entry.code,)).fetchone()
        if existing is None:
            next_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 AS next FROM watchlist"
            ).fetchone()["next"]
            _insert(conn, WatchlistEntry(entry.code, entry.name, entry.added_at, kind), next_order)
            created = True
        else:
            conn.execute(
                "UPDATE watchlist SET name = ?, kind = ? WHERE code = ?",
                (entry.name, kind, entry.code),
            )
            created = False
        conn.execute("COMMIT")
        return created
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _insert(conn: sqlite3.Connection, entry: WatchlistEntry, order: int) -> None:
    kind = entry.kind if entry.kind in KINDS else KIND_STOCK
    conn.execute(
        "INSERT INTO watchlist (code, name, kind, added_at, sort_order) VALUES (?, ?, ?, ?, ?)",
        (entry.code, entry.name, kind, entry.added_at, order),
    )


def _row_to_entry(row: sqlite3.Row) -> WatchlistEntry:
    kind = str(row["kind"] or KIND_STOCK)
    return WatchlistEntry(
        code=row["code"],
        name=str(row["name"] or ""),
        added_at=str(row["added_at"] or ""),
        # 库里有 CHECK 约束，这里再兜一层：读到意外值时按股票处理，不让整份清单崩掉
        kind=kind if kind in KINDS else KIND_STOCK,
    )


def _import_legacy(conn: sqlite3.Connection, meta_dir: Path | str) -> None:
    """把旧版 `watchlist.json` 导入一次，成功后改名，避免清空自选后又被重新导入。"""
    path = legacy_path(meta_dir)
    if not path.is_file():
        return
    if conn.execute("SELECT COUNT(*) AS count FROM watchlist").fetchone()["count"]:
        # 表里已有数据：说明早迁过了，这个文件只能是后来被手工放回来的，不再理会
        return

    entries = _parse_legacy(path)
    conn.execute("BEGIN IMMEDIATE")
    try:
        for order, entry in enumerate(entries, start=1):
            _insert(conn, entry, order)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    migrated = path.with_name(path.name + MIGRATED_SUFFIX)
    os.replace(path, migrated)
    logger.info("自选清单已从 %s 迁移进 meta.db，原文件保留为 %s", path, migrated)


def _parse_legacy(path: Path) -> list[WatchlistEntry]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WatchlistCorruptError(f"旧版自选文件损坏或不可读：{path}") from exc

    if not isinstance(raw, dict):
        raise WatchlistCorruptError(f"旧版自选文件结构不合法：{path}")
    items = raw.get("items") or []
    if not isinstance(items, list):
        raise WatchlistCorruptError(f"旧版自选文件结构不合法：{path}")

    entries: list[WatchlistEntry] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise WatchlistCorruptError(f"旧版自选文件结构不合法：{path}")
        code = str(item.get("code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        kind = str(item.get("kind") or KIND_STOCK).strip().lower()
        entries.append(
            WatchlistEntry(
                code=code,
                name=str(item.get("name") or ""),
                added_at=str(item.get("addedAt") or ""),
                # 旧文件没有 kind 字段：一律按股票处理，向后兼容
                kind=kind if kind in KINDS else KIND_STOCK,
            )
        )
    return entries
