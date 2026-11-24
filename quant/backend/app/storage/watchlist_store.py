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


@dataclass(frozen=True)
class WatchlistEntry:
    code: str
    name: str
    added_at: str

    def as_dict(self) -> dict:
        return {"code": self.code, "name": self.name, "addedAt": self.added_at}


def load_watchlist(meta_dir: Path | str) -> list[WatchlistEntry]:
    path = Path(meta_dir) / WATCHLIST_FILENAME
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # 自选损坏时按空处理，不阻断服务启动；下次写入会覆盖成合法结构
        return []

    entries: list[WatchlistEntry] = []
    seen: set[str] = set()
    for item in raw.get("items") or []:
        code = str(item.get("code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        entries.append(
            WatchlistEntry(
                code=code,
                name=str(item.get("name") or ""),
                added_at=str(item.get("addedAt") or ""),
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
