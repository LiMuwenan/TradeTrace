# -*- coding: utf-8 -*-
"""指数日线的 Parquet 读写：**一个指数一个文件**（`<根目录>/<code>.parquet`）。

为什么不像股票那样按年分区：股票的取数是「按日拉全市场」，天然按日/年聚拢；指数只能
「按单只 + 日期区间」取，写入单位本来就是一只指数。一只指数一个文件后，回补某一只只
重写它自己（不碰其他指数），详情页也只读一个文件。

与股票目录分开（`parquet/index/`），因为两者的列不同：指数没有停牌标记、换手、估值，
也没有复权因子；硬塞进 19 列 schema 会往行情契约里塞一堆「不适用」的空列。
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from pyarrow import Table

from app.storage.schema import INDEX_COLUMNS, INDEX_SCHEMA, normalize_index_code


class IndexStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def path(self, code: str) -> Path:
        return self.root / f"{normalize_index_code(code)}.parquet"

    def codes(self) -> list[str]:
        """已入库的指数代码，按代码升序。"""
        if not self.root.is_dir():
            return []
        return sorted(path.stem for path in self.root.glob("*.parquet"))

    def merge(self, code: str, rows: pd.DataFrame) -> int:
        """把新行并入该指数的文件，按日期覆盖旧行；返回写入行数。"""
        if rows.empty:
            return 0

        path = self.path(code)
        path.parent.mkdir(parents=True, exist_ok=True)
        incoming = rows[INDEX_COLUMNS].reset_index(drop=True)

        if path.is_file():
            old = pd.read_parquet(path)
            merged = pd.concat([old[INDEX_COLUMNS], incoming], ignore_index=True)
        else:
            merged = incoming

        # 新行在后，keep="last" 即「同一天以后写入的为准」
        merged = merged.drop_duplicates(subset=["date"], keep="last")
        merged = merged.sort_values("date", kind="mergesort").reset_index(drop=True)

        table = Table.from_pandas(merged, preserve_index=False).cast(INDEX_SCHEMA)
        tmp_path = path.with_name(f".{path.name}.tmp")
        try:
            pq.write_table(table, tmp_path, compression="zstd")
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)
        return len(incoming)

    def series(self, code: str) -> list[dict]:
        """该指数的逐日序列，按日期升序；无数据返回空列表。"""
        path = self.path(code)
        if not path.is_file():
            return []
        frame = pd.read_parquet(path, columns=INDEX_COLUMNS).sort_values("date")
        return [
            {
                "date": row.date,
                "code": row.code,
                "open": _none_if_nan(row.open),
                "high": _none_if_nan(row.high),
                "low": _none_if_nan(row.low),
                "close": _none_if_nan(row.close),
                "preclose": _none_if_nan(row.preclose),
                "volume": _none_if_nan(row.volume),
                "amount": _none_if_nan(row.amount),
                "pctChg": _none_if_nan(row.pctChg),
            }
            for row in frame.itertuples(index=False)
        ]

    def latest_bars(self, codes: list[str]) -> dict[str, dict]:
        """每只指数的最新一行，用于自选列表摘要。"""
        quotes: dict[str, dict] = {}
        for code in dict.fromkeys(codes):
            series = self.series(code)
            if not series:
                continue
            last = series[-1]
            quotes[code] = {
                "date": last["date"],
                "close": last["close"],
                "pctChg": last["pctChg"],
                # 指数没有停牌标记：数据源当天没返回就是没有这一行
                "suspended": False,
            }
        return quotes

    def last_date(self, code: str) -> str | None:
        path = self.path(code)
        if not path.is_file():
            return None
        frame = pd.read_parquet(path, columns=["date"])
        if frame.empty:
            return None
        return str(frame["date"].max())

    def has_date(self, code: str, trade_date: str) -> bool:
        path = self.path(code)
        if not path.is_file():
            return False
        frame = pd.read_parquet(path, columns=["date"], filters=[("date", "==", trade_date)])
        return not frame.empty


def _none_if_nan(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
