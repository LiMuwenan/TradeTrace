# -*- coding: utf-8 -*-
"""指数清单：代码 → 名称，用户数据，存放在 `meta_dir/index_catalog.json`。

为什么不用股票名称缓存：那份缓存只收 `type=1`（股票）的证券，指数被明确滤掉
（见 `stock_names.py`）。指数数量是个位数，与其每次翻页拉全市场再筛，不如本地留一份
可扩展清单：种子 8 条覆盖主要宽基与风格指数，用户添加清单外的指数时按代码补一条。

文件存在时**整份以文件为准**，不再合并种子——否则用户删掉的指数会在下次读取时复活。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from app.storage.schema import normalize_index_code

logger = logging.getLogger(__name__)

CATALOG_FILENAME = "index_catalog.json"

# 种子清单：改动这里只影响「首次生成」的文件，已有文件不受影响
SEED_INDICES: tuple[tuple[str, str], ...] = (
    ("sh.000001", "上证指数"),
    ("sz.399001", "深证成指"),
    ("sz.399006", "创业板指"),
    ("sh.000688", "科创50"),
    ("sh.000300", "沪深300"),
    ("sh.000016", "上证50"),
    ("sh.000905", "中证500"),
    ("sh.000852", "中证1000"),
)


def catalog_path(meta_dir: Path | str) -> Path:
    return Path(meta_dir) / CATALOG_FILENAME


def load_catalog(meta_dir: Path | str) -> dict[str, str]:
    """读取指数清单；文件缺失时返回种子，损坏时告警并退回种子（不覆盖原文件）。"""
    path = catalog_path(meta_dir)
    if not path.is_file():
        return dict(SEED_INDICES)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("指数清单损坏，暂时按种子清单处理：%s", exc)
        return dict(SEED_INDICES)

    items = raw.get("items") if isinstance(raw, dict) else None
    if not isinstance(items, dict):
        logger.warning("指数清单结构不合法，暂时按种子清单处理：%s", path)
        return dict(SEED_INDICES)

    catalog: dict[str, str] = {}
    for code, name in items.items():
        try:
            catalog[normalize_index_code(code)] = str(name or "")
        except Exception:  # noqa: BLE001 单条坏数据不应让整份清单不可用
            continue
    return catalog or dict(SEED_INDICES)


def save_catalog(meta_dir: Path | str, catalog: dict[str, str]) -> None:
    path = catalog_path(meta_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"items": {code: name for code, name in sorted(catalog.items())}}
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def upsert_index(meta_dir: Path | str, raw_code: str, name: str = "") -> tuple[str, dict[str, str]]:
    """把指数写进清单（已存在则仅在名称更好时更新），返回 (归一化代码, 清单)。"""
    code = normalize_index_code(raw_code)
    catalog = load_catalog(meta_dir)
    current = catalog.get(code)
    if current is None:
        catalog[code] = name
        save_catalog(meta_dir, catalog)
    elif name and name != current:
        catalog[code] = name
        save_catalog(meta_dir, catalog)
    return code, catalog


def is_index_code(meta_dir: Path | str, raw_code: str) -> bool:
    """该代码是否属于指数。裸代码一律返回 False（不猜，避免把股票认成指数）。"""
    try:
        code = normalize_index_code(raw_code)
    except Exception:  # noqa: BLE001 带前缀的股票代码也会被这里挡下
        return False
    return code in load_catalog(meta_dir)
