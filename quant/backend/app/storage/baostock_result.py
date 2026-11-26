# -*- coding: utf-8 -*-
"""baostock 结果集读取。

绕开 `ResultData.get_data()`：该方法在翻页时用 `DataFrame.append` 合并分页数据，
而这个 API 在 pandas 2.0 就被删除了（本项目依赖 pandas>=2.2，实测 3.x），
于是只要结果超过一页就会抛 `AttributeError: 'DataFrame' object has no attribute 'append'`。
官方示例中的 `while rs.next(): rs.get_row_data()` 逐行取数不碰 DataFrame，
任何 pandas 版本都能用，分页也由 `next()` 自己处理。
"""
from __future__ import annotations

from app.storage.schema import IngestError


def collect_rows(result) -> list[list[str]]:
    """把结果集逐行读干，返回 `list[list[str]]`；列顺序以 `result.fields` 为准。

    翻页中途出错时抛 IngestError：半份行情比报错更危险，调用方不应该拿到残缺结果。
    """
    rows: list[list[str]] = []
    while result.error_code == "0" and result.next():
        row = result.get_row_data()
        if row:
            rows.append(row)
    if result.error_code != "0":
        raise IngestError(f"baostock 读取结果失败：{result.error_msg}")
    return rows
