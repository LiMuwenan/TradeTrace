# -*- coding: utf-8 -*-
"""年份分区 Parquet 的读写。写入只由 `Ingestor` 调用，禁止在别处另开写路径。

- 文件名 `<年份>.parquet`，一个文件内含当年全市场标的；
- 文件内按 (标的, 日期) 排序，便于列裁剪与 row-group 统计；
- 写临时文件再 `os.replace`，进程中断不会留下半个年份文件；
- 查询用 DuckDB 直读，不引入独立数据库服务。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow.parquet as pq
from pyarrow import Table

from app.storage.schema import STORE_COLUMNS, STORE_SCHEMA

ROW_GROUP_SIZE = 122_880


@dataclass(frozen=True)
class MergeResult:
    """一次写入的结果：写入行数与其中覆盖掉的已有行数。"""

    rows: int
    replaced: int


class ParquetStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def year_path(self, year: int) -> Path:
        return self.root / f"{year}.parquet"

    def year_files(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return sorted(self.root.glob("*.parquet"))

    def has_date(self, trade_date: str) -> bool:
        """该交易日是否已有数据入库。

        只读当年文件：日 K 不会跨年归档，查 2026-11-26 时去扫 2025 的文件没有意义。
        """
        path = self.year_path(int(trade_date[:4]))
        if not path.is_file():
            return False
        sql = f"SELECT 1 FROM read_parquet(?) WHERE date = ? LIMIT 1"
        return not self._query(sql, [str(path), trade_date]).empty

    def merge(self, rows: pd.DataFrame) -> MergeResult:
        """把新行并入对应年份文件，按 (标的, 日期) 覆盖旧行。"""
        if rows.empty:
            return MergeResult(rows=0, replaced=0)

        self.root.mkdir(parents=True, exist_ok=True)
        years = rows["date"].str.slice(0, 4)
        replaced = 0
        for year, part in rows.groupby(years, sort=True):
            replaced += self._merge_year(int(year), part)
        return MergeResult(rows=len(rows), replaced=replaced)

    def _merge_year(self, year: int, new_rows: pd.DataFrame) -> int:
        """并入一个年份文件，返回被覆盖的已有行数。"""
        path = self.year_path(year)
        incoming = new_rows[STORE_COLUMNS].reset_index(drop=True)

        if path.is_file():
            old = pd.read_parquet(path)
            existing_rows = len(old)
            merged = pd.concat([old[STORE_COLUMNS], incoming], ignore_index=True)
        else:
            existing_rows = 0
            merged = incoming

        # 新行在后，keep="last" 即“同一标的同一天以后写入的为准”
        merged = merged.drop_duplicates(subset=["code", "date"], keep="last")
        merged = merged.sort_values(["code", "date"], kind="mergesort").reset_index(drop=True)

        table = Table.from_pandas(merged, preserve_index=False).cast(STORE_SCHEMA)
        tmp_path = path.with_name(f".{path.name}.tmp")
        try:
            pq.write_table(table, tmp_path, compression="zstd", row_group_size=ROW_GROUP_SIZE)
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)

        return existing_rows + len(incoming) - len(merged)

    def last_bars(self, before: str) -> dict[str, dict]:
        """取每个标的在 `before` 之前（不含）的最后一行，用于因子前向填充。"""
        files = self.year_files()
        if not files:
            return {}

        sql = f"""
            SELECT code, date, close, back_factor
            FROM (
                SELECT code, date, close, back_factor,
                       row_number() OVER (PARTITION BY code ORDER BY date DESC) AS rn
                FROM {self._read_sql()}
                WHERE date < ?
            )
            WHERE rn = 1
        """
        frame = self._query(sql, [before])
        return {
            row.code: {"date": row.date, "close": _none_if_nan(row.close), "factor": row.back_factor}
            for row in frame.itertuples(index=False)
        }

    def latest_bars(self, codes: list[str]) -> dict[str, dict]:
        """取每个标的的最新一行，用于自选列表的行情摘要。"""
        wanted = list(dict.fromkeys(codes))
        files = self.year_files()
        if not wanted or not files:
            return {}

        placeholders = ", ".join("?" for _ in wanted)
        sql = f"""
            SELECT code, date, close, pctChg, tradestatus
            FROM (
                SELECT code, date, close, pctChg, tradestatus,
                       row_number() OVER (PARTITION BY code ORDER BY date DESC) AS rn
                FROM {self._read_sql()}
                WHERE code IN ({placeholders})
            )
            WHERE rn = 1
        """
        frame = self._query(sql, wanted)
        return {
            row.code: {
                "date": row.date,
                "close": _none_if_nan(row.close),
                "pctChg": _none_if_nan(row.pctChg),
                "suspended": int(row.tradestatus) == 0,
            }
            for row in frame.itertuples(index=False)
        }

    def codes(self) -> list[str]:
        """已入库的全部标的代码，按代码升序。"""
        files = self.year_files()
        if not files:
            return []
        frame = self._query(f"SELECT DISTINCT code FROM {self._read_sql()} ORDER BY code")
        return frame["code"].tolist()

    def series(self, code: str, start: str | None = None, end: str | None = None) -> list[dict]:
        """按标的读取逐日序列，附带后复权价。"""
        files = self.year_files()
        if not files:
            return []

        conditions = ["code = ?"]
        params: list[object] = [code]
        if start:
            conditions.append("date >= ?")
            params.append(start)
        if end:
            conditions.append("date <= ?")
            params.append(end)

        sql = f"""
            SELECT {', '.join(STORE_COLUMNS)}
            FROM {self._read_sql()}
            WHERE {' AND '.join(conditions)}
            ORDER BY date
        """
        frame = self._query(sql, params)
        return [_series_row(row) for row in frame.itertuples(index=False)]

    def stats(self) -> dict:
        """总行数、日期范围、各年份行数。空库返回 0 与 null。"""
        files = self.year_files()
        if not files:
            return {"totalRows": 0, "dateRange": {"start": None, "end": None}, "years": []}

        sql = f"""
            SELECT substr(date, 1, 4) AS year, count(*) AS row_count,
                   min(date) AS start_date, max(date) AS end_date
            FROM {self._read_sql()}
            GROUP BY 1
            ORDER BY 1
        """
        frame = self._query(sql)
        years = [
            {
                "year": int(row.year),
                "rows": int(row.row_count),
                "startDate": row.start_date,
                "endDate": row.end_date,
            }
            for row in frame.itertuples(index=False)
        ]
        return {
            "totalRows": sum(item["rows"] for item in years),
            "dateRange": {"start": years[0]["startDate"], "end": years[-1]["endDate"]},
            "years": years,
        }

    def stored_dates(self) -> set[str]:
        files = self.year_files()
        if not files:
            return set()
        frame = self._query(f"SELECT DISTINCT date FROM {self._read_sql()} ORDER BY date")
        return set(frame["date"].tolist())

    def _read_sql(self) -> str:
        glob = str(self.root / "*.parquet").replace("\\", "/").replace("'", "''")
        return f"read_parquet('{glob}', union_by_name = true)"

    @staticmethod
    def _query(sql: str, params: list[object] | None = None) -> pd.DataFrame:
        connection = duckdb.connect()
        try:
            return connection.execute(sql, params or []).fetchdf()
        finally:
            connection.close()


def _series_row(row) -> dict:
    factor = float(row.back_factor)
    close = _none_if_nan(row.close)
    return {
        "date": row.date,
        "code": row.code,
        "open": _none_if_nan(row.open),
        "high": _none_if_nan(row.high),
        "low": _none_if_nan(row.low),
        "close": close,
        "preclose": _none_if_nan(row.preclose),
        "volume": _none_if_nan(row.volume),
        "amount": _none_if_nan(row.amount),
        "turn": _none_if_nan(row.turn),
        "tradestatus": int(row.tradestatus),
        "pctChg": _none_if_nan(row.pctChg),
        "isST": int(row.isST),
        "backFactor": factor,
        # 后复权价 = 不复权价 × 当行因子；停牌行价格保留但求值方需排除
        "adjOpen": _adjusted(row.open, factor),
        "adjHigh": _adjusted(row.high, factor),
        "adjLow": _adjusted(row.low, factor),
        "adjClose": _adjusted(row.close, factor),
    }


def _none_if_nan(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _adjusted(value: object, factor: float) -> float | None:
    raw = _none_if_nan(value)
    return None if raw is None else round(raw * factor, 4)
