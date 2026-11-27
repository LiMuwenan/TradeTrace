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

# 指数日线只存 10 列：核心价格/量额/涨跌幅。请求 18 列虽然也能返回，但估值列全是 0、
# `tradestatus` 恒为 1、`isST` 恒为 0、`turn` 对指数没有确定分母——存进来只是占位噪声。
INDEX_COLUMNS = [
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "preclose",
    "volume",
    "amount",
    "pctChg",
]

INDEX_SCHEMA = pa.schema(
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
        ("pctChg", pa.float64()),
    ]
)

_CODE_RE = re.compile(r"(?i)^(?:(sh|sz|bj)[.\-]?)?(\d{6})(?:[.\-](sh|sz|bj))?$")

# 指数代码必须自带前缀：裸 6 位数字会按首位推断成股票（000001 是平安银行，不是上证指数）
_INDEX_CODE_RE = re.compile(r"(?i)^(?:(sh|sz|bj)[.\-]?(\d{6})|(\d{6})[.\-](sh|sz|bj))$")

_MIN_GAP_ITEMS = 5


class IngestError(RuntimeError):
    """数据不合格，拒绝写入。消息面向用户，可直接展示。"""


class CodeFormatError(IngestError):
    """标的代码写法不合法（区别于「代码合法但查不到数据」）。

    接口层据此把「格式错」统一成一句提示，而把「这个代码需要带前缀」这类
    更有用的信息原样透出。
    """


class NoMarketDataError(IngestError):
    """数据源在该交易日没有返回任何数据：非交易日，或接口异常。

    调度据此把当天判为「跳过」而不是「失败」——票面约定不对接交易日历，
    只以数据源是否返回当日数据来判定（见 10 号票）。
    """


def normalize_code(raw: object) -> str:
    """把各种写法的标的代码归一为 `sh.600000` / `sz.000001`。

    支持 `sh.600000`、`600000.SH`、`sh600000`、`600000`；无前缀时按首位推断交易所。
    """
    text = str(raw).strip()
    match = _CODE_RE.match(text)
    if not match:
        raise CodeFormatError(f"无法识别的标的代码：{raw!r}（应形如 sh.600000）")

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
            raise CodeFormatError(f"无法从代码推断交易所：{raw!r}")
    return f"{prefix}.{digits}"


def normalize_index_code(raw: object) -> str:
    """指数代码归一，**必须自带市场前缀**。

    指数与股票共用 6 位数字空间（`000001` 既是上证指数也是平安银行），裸代码只能靠推断，
    而推断规则是按首位分交易所，必然把 `000001` 判成 `sz.000001`。所以这里拒绝裸代码，
    宁可让调用方补上前缀，也不接受一个「看起来合法」的错误代码。
    """
    text = str(raw).strip()
    match = _INDEX_CODE_RE.match(text)
    if not match:
        raise CodeFormatError(f"指数代码必须带市场前缀，如 sh.000001：{raw!r}")
    prefix = (match.group(1) or match.group(4) or "").lower()
    digits = match.group(2) or match.group(3)
    return f"{prefix}.{digits}"
