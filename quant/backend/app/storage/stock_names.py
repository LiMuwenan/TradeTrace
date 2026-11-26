# -*- coding: utf-8 -*-
"""股票名称字典：代码 → 名称，来源为 baostock 的全市场证券清单。

名称不在日 K 的 18 列里，因此单独维护一份缓存（`meta_dir/stock_names.json`）。
搜索时若缓存缺失或过期会尝试刷新；刷新失败时退回「只按代码搜索」，不阻断使用。
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from app.storage.baostock_result import collect_rows
from app.storage.schema import IngestError, normalize_code

CACHE_FILENAME = "stock_names.json"
CACHE_TTL = timedelta(days=1)

logger = logging.getLogger(__name__)


class NameProvider(Protocol):
    """名称来源的最小接口；测试用假实现替换，不访问网络。"""

    def fetch_names(self) -> dict[str, str]:
        """返回 `{归一化代码: 名称}`；失败时抛 IngestError。"""


class BaostockNameProvider:
    """baostock `query_stock_basic` 实现：一次调用拿全市场证券清单。"""

    def fetch_names(self) -> dict[str, str]:
        try:
            import baostock as bs
        except ImportError as exc:  # pragma: no cover - 依赖缺失时的可操作提示
            raise IngestError("未安装 baostock，无法获取股票名称；请先 pip install baostock") from exc

        login = bs.login()
        if login.error_code != "0":
            raise IngestError(f"baostock 登录失败：{login.error_msg}")
        try:
            result = bs.query_stock_basic()
            if result.error_code != "0":
                raise IngestError(f"baostock 证券清单查询失败：{result.error_msg}")
            # 不用 result.get_data()：它翻页时用 pandas 已删除的 DataFrame.append
            rows = collect_rows(result)
            fields = list(result.fields)
        finally:
            bs.logout()

        index = {name: position for position, name in enumerate(fields)}
        names: dict[str, str] = {}
        for row in rows:
            # 只要正常上市的股票（type=1 股票，status=1 上市），排除指数与退市标的
            if _field(row, index, "type", "1") != "1":
                continue
            if _field(row, index, "status", "1") != "1":
                continue
            name = _field(row, index, "code_name", "").strip()
            if not name:
                continue
            try:
                names[normalize_code(_field(row, index, "code", ""))] = name
            except IngestError:
                continue
        if not names:
            raise IngestError("baostock 返回的证券清单为空，未刷新名称缓存")
        return names


class StockNameCache:
    """带磁盘缓存的名称字典。缓存只由本类读写。"""

    def __init__(self, meta_dir: Path | str, provider: NameProvider | None = None) -> None:
        self.path = Path(meta_dir) / CACHE_FILENAME
        self.provider = provider
        # 联网刷新同一时刻只跑一次：baostock 客户端是进程级全局 socket，并发登录会互相踢会话，
        # 而且整份清单要翻好几页（实测约 1 分钟），重复刷新纯属浪费
        self._refresh_lock = threading.Lock()

    def names(self) -> dict[str, str]:
        """只读缓存，不访问网络。"""
        cached = self._read_cache()
        return cached[0] if cached else {}

    def ensure(self) -> dict[str, str]:
        """缓存缺失或过期时刷新；刷新失败则退回旧缓存（没有则空）。"""
        cached = self._read_cache()
        if cached is not None and not self._expired(cached[1]):
            return cached[0]
        if self.provider is None:
            return cached[0] if cached else {}
        with self._refresh_lock:
            # 等锁期间可能已被别的线程（如启动预热）刷新好，拿到锁后重新判一次
            cached = self._read_cache()
            if cached is not None and not self._expired(cached[1]):
                return cached[0]
            try:
                return self.refresh()
            except Exception as exc:  # 名称字典是尽力而为的外部依赖，失败不应阻断自选与搜索
                logger.warning("股票名称字典刷新失败，沿用旧缓存：%s", exc)
                return cached[0] if cached else {}

    def warm_up(self) -> None:
        """启动预热：缓存过期就在后台刷新，不让第一次搜索替这次联网等待。

        整份证券清单要翻几页，冷启动约一分钟；放到后台线程后，服务照常接请求，
        这段窗口内名称只有旧缓存（没有则退回按代码搜索）。
        """
        cached = self._read_cache()
        if cached is not None and not self._expired(cached[1]):
            return
        if self.provider is None:
            return
        threading.Thread(
            target=self._warm_up_worker, name="stock-names-warmup", daemon=True
        ).start()

    def _warm_up_worker(self) -> None:
        # ensure 自己会兜住所有异常并降级，这里不再重复处理
        self.ensure()

    def refresh(self) -> dict[str, str]:
        if self.provider is None:
            raise IngestError("未配置股票名称来源")
        names = self.provider.fetch_names()
        self._write_cache(names)
        return names

    def _read_cache(self) -> tuple[dict[str, str], str] | None:
        if not self.path.is_file():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        names = {
            str(code): str(name)
            for code, name in (raw.get("names") or {}).items()
            if str(code) and str(name)
        }
        return names, str(raw.get("generatedAt") or "")

    def _write_cache(self, names: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "names": names,
        }
        tmp_path = self.path.with_name(f".{self.path.name}.tmp")
        try:
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp_path, self.path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def _expired(self, generated_at: str) -> bool:
        try:
            created = datetime.fromisoformat(generated_at)
        except ValueError:
            return True
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - created > CACHE_TTL


def _field(row: object, index: dict[str, int], name: str, default: str) -> str:
    position = index.get(name)
    if position is None:
        return default
    return str(row[position])
