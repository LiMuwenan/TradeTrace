# -*- coding: utf-8 -*-
"""自选清单的持久化：单用户、全局唯一一份，按添加顺序保存。

自选是用户数据，不能像 Parquet 那样从原始 CSV 重建，因此放在 `meta_dir`，
与可重建的行情索引分开。写入走临时文件 + 原子替换，进程中断不会留下半个文件。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

WATCHLIST_FILENAME = "watchlist.json"

# 自选标的类型：股票与指数共用一份清单，靠这个字段区分行情来源
KIND_STOCK = "stock"
KIND_INDEX = "index"
KINDS = (KIND_STOCK, KIND_INDEX)


class WatchlistCorruptError(Exception):
    """自选文件存在但无法读取或解析。

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
    path = Path(meta_dir) / WATCHLIST_FILENAME
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WatchlistCorruptError(f"自选文件损坏或不可读：{path}") from exc

    if not isinstance(raw, dict):
        raise WatchlistCorruptError(f"自选文件结构不合法：{path}")
    items = raw.get("items") or []
    if not isinstance(items, list):
        raise WatchlistCorruptError(f"自选文件结构不合法：{path}")

    entries: list[WatchlistEntry] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise WatchlistCorruptError(f"自选文件结构不合法：{path}")
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


def save_watchlist(meta_dir: Path | str, entries: list[WatchlistEntry]) -> None:
    root = Path(meta_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / WATCHLIST_FILENAME
    payload = {"items": [entry.as_dict() for entry in entries]}
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)
