# -*- coding: utf-8 -*-
"""名称字典缓存：启动预热不阻塞、不重复联网。"""
from __future__ import annotations

import threading
import time

from app.storage.stock_names import StockNameCache

NAMES = {"sh.600519": "贵州茅台"}


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.started = threading.Event()

    def fetch_names(self) -> dict[str, str]:
        self.calls += 1
        self.started.set()
        return dict(NAMES)


def test_warm_up_leaves_fresh_cache_alone(tmp_path):
    provider = CountingProvider()
    cache = StockNameCache(tmp_path, provider)
    cache.refresh()

    cache.warm_up()

    assert provider.calls == 1  # 缓存还没过期，预热不该再联网


def test_warm_up_refreshes_in_background_without_blocking(tmp_path):
    provider = CountingProvider()
    cache = StockNameCache(tmp_path, provider)

    cache.warm_up()  # 立即返回，联网在后台线程

    assert provider.started.wait(5), "预热线程没有启动"
    deadline = time.time() + 5
    while time.time() < deadline and not cache.names():
        time.sleep(0.02)
    assert cache.names() == NAMES


def test_missing_provider_never_spawns_refresh(tmp_path):
    cache = StockNameCache(tmp_path, None)

    cache.warm_up()

    assert cache.names() == {}
