# -*- coding: utf-8 -*-
"""存储元数据：每个标的的因子基准（scales）与最近一次导入结果。

单独落一个小 JSON，避免为了拿基准去扫全部 Parquet。写入同样走临时文件 + 原子替换。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

STATE_FILENAME = "store_state.json"


@dataclass
class StoreState:
    scales: dict[str, float] = field(default_factory=dict)
    last_run: dict | None = None


def load_state(parquet_dir: Path | str) -> StoreState:
    path = Path(parquet_dir) / STATE_FILENAME
    if not path.is_file():
        return StoreState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # 状态可重建，损坏时从空开始，不阻断行情数据本身
        return StoreState()
    scales = {str(code): float(value) for code, value in (raw.get("scales") or {}).items()}
    return StoreState(scales=scales, last_run=raw.get("lastRun"))


def save_state(parquet_dir: Path | str, state: StoreState) -> None:
    root = Path(parquet_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / STATE_FILENAME
    payload = {"scales": state.scales, "lastRun": state.last_run}
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)
