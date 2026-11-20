# -*- coding: utf-8 -*-
"""行情数据的存储契约：列定义、类型与标的代码规范化。

数据源（baostock）的日 K 是 18 列不复权数据；落盘时额外加一列每行的后复权因子
`back_factor`，不存任何复权后的价格。
"""
from __future__ import annotations

import re

import pyarrow as pa

# 日 K 源文件与实时接口的 18 列，顺序与 baostock 一致
DAILY_COLUMNS = [
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "preclose",
    "volume",
    "amount",
    "adjustflag",
    "turn",
    "tradestatus",
    "pctChg",
    "peTTM",
    "pbMRQ",
    "psTTM",
    "pcfNcfTTM",
    "isST",
]

# 除权清单的 5 列；其中只有 backAdjustFactor 会入存储（前复权因子不入库）
FACTOR_COLUMNS = ["code", "dividOperateDate", "foreAdjustFactor", "backAdjustFactor", "adjustFactor"]

STORE_COLUMNS = [*DAILY_COLUMNS, "back_factor"]

STORE_SCHEMA = pa.schema(
    [
        ("date", pa.string()),
        ("code", pa.string()),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("preclose", pa.float64()),
        ("volume", pa.float64()),
        ("amount", pa.float64()),
        ("adjustflag", pa.int8()),
        ("turn", pa.float64()),
        ("tradestatus", pa.int8()),
        ("pctChg", pa.float64()),
        ("peTTM", pa.float64()),
        ("pbMRQ", pa.float64()),
        ("psTTM", pa.float64()),
        ("pcfNcfTTM", pa.float64()),
        ("isST", pa.int8()),
        ("back_factor", pa.float64()),
    ]
)

_CODE_RE = re.compile(r"(?i)^(?:(sh|sz|bj)[.\-]?)?(\d{6})(?:[.\-](sh|sz|bj))?$")

_MIN_GAP_ITEMS = 5


class IngestError(RuntimeError):
    """数据不合格，拒绝写入。消息面向用户，可直接展示。"""


def normalize_code(raw: object) -> str:
    """把各种写法的标的代码归一为 `sh.600000` / `sz.000001`。

    支持 `sh.600000`、`600000.SH`、`sh600000`、`600000`；无前缀时按首位推断交易所。
    """
    text = str(raw).strip()
    match = _CODE_RE.match(text)
    if not match:
        raise IngestError(f"无法识别的标的代码：{raw!r}（应形如 sh.600000）")

    prefix = (match.group(1) or match.group(3) or "").lower()
    digits = match.group(2)
    if not prefix:
        if digits.startswith("6"):
            prefix = "sh"
        elif digits.startswith(("0", "3")):
            prefix = "sz"
        elif digits.startswith(("4", "8", "9")):
            prefix = "bj"
        else:
            raise IngestError(f"无法从代码推断交易所：{raw!r}")
    return f"{prefix}.{digits}"
