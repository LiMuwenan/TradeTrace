# -*- coding: utf-8 -*-
"""baostock 结果集读取：不依赖 pandas 已删除的 DataFrame.append。

回归点：`ResultData.get_data()` 翻页时用 `df.append(...)`，pandas 2.0 起已删除，
结果超过一页就抛 AttributeError，证券清单因此刷不出来（名称字典永远为空、搜索只剩代码）。
"""
from __future__ import annotations

import sys

import pytest

from app.storage.baostock_result import collect_rows
from app.storage.schema import IngestError
from app.storage.stock_names import BaostockNameProvider


class FakeResult:
    """按页交付的结果集；调用 get_data() 直接失败，确保实现没走回旧路径。"""

    def __init__(self, pages: list[list[list[str]]], fields: list[str]) -> None:
        self.fields = fields
        self.error_code = "0"
        self.error_msg = ""
        self._pages = pages
        self._page = 0
        self._row = 0

    def next(self) -> bool:
        while self._page < len(self._pages) and self._row >= len(self._pages[self._page]):
            self._page += 1
            self._row = 0
        return self._page < len(self._pages)

    def get_row_data(self) -> list[str]:
        row = self._pages[self._page][self._row]
        self._row += 1
        return row

    def get_data(self):  # pragma: no cover - 被调用即说明回退到了有问题的实现
        raise AssertionError("不应调用 get_data()：它依赖已被 pandas 删除的 DataFrame.append")


def test_collect_rows_spans_multiple_pages():
    result = FakeResult([[["sh.600519", "贵州茅台"]], [["sz.000001", "平安银行"]]], ["code", "code_name"])

    assert collect_rows(result) == [["sh.600519", "贵州茅台"], ["sz.000001", "平安银行"]]


def test_collect_rows_reports_failure_instead_of_partial_data():
    class Failing(FakeResult):
        def next(self) -> bool:
            self.error_code = "10001"
            self.error_msg = "网络断开"
            return False

    with pytest.raises(IngestError, match="网络断开"):
        collect_rows(Failing([[["sh.600519", "贵州茅台"]]], ["code", "code_name"]))


def test_name_provider_reads_rows_without_get_data(monkeypatch):
    """证券清单超过一页时也必须能刷出名称，且不触碰 get_data()。"""
    fields = ["code", "code_name", "ipoDate", "outDate", "type", "status"]
    pages = [
        [["sh.600519", "贵州茅台", "2001-08-27", "", "1", "1"]],
        [
            ["sz.000001", "平安银行", "1991-04-03", "", "1", "1"],
            ["sh.000001", "上证指数", "1991-07-15", "", "2", "1"],  # 指数不入字典
            ["sz.000002", "已退市", "1991-01-29", "2020-01-01", "1", "0"],  # 已退市不入字典
        ],
    ]

    class FakeLogin:
        error_code = "0"
        error_msg = ""

    class FakeBaostock:
        def login(self):
            return FakeLogin()

        def logout(self):
            return FakeLogin()

        def query_stock_basic(self):
            return FakeResult(pages, fields)

    monkeypatch.setitem(sys.modules, "baostock", FakeBaostock())

    assert BaostockNameProvider().fetch_names() == {
        "sh.600519": "贵州茅台",
        "sz.000001": "平安银行",
    }
