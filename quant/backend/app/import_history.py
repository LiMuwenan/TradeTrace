# -*- coding: utf-8 -*-
"""历史数据导入命令：

    python -m app.import_history [历史目录]

不指定目录时读取 config.toml 的 `data.raw_dir`。目录内约定
`daily/YYYY-MM-DD.csv` 与 `factor(s)/YYYY.csv`（没有 daily/ 时直接读根目录）；
按日归档的除权文件 `YYYY-MM-DD.csv` 仍兼容。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from app.config import load_settings
from app.storage.ingest import Ingestor
from app.storage.schema import IngestError
from app.storage.sources import HistoricalCsvSource


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入历史日 K 与除权清单")
    parser.add_argument("source", nargs="?", help="历史 CSV 目录，默认 config 的 raw_dir")
    args = parser.parse_args(argv)

    settings = load_settings()
    source_dir = Path(args.source) if args.source else settings.raw_dir

    try:
        source = HistoricalCsvSource(source_dir)
    except IngestError as exc:
        print(f"无法读取历史数据：{exc}")
        return 1

    print(f"历史目录：{source_dir}")
    print(f"交易日数量：{len(source.dates())}（{source.dates()[0]} ~ {source.dates()[-1]}）")

    ingestor = Ingestor(settings)
    try:
        reports = ingestor.import_history(source)
    except IngestError as exc:
        print(f"导入失败：{exc}")
        return 1

    for report in reports:
        years = sorted({trade_date[:4] for trade_date in report.trade_dates})
        print(
            f"{'/'.join(years)}：{len(report.trade_dates)} 个交易日，写入 {report.rows} 行"
            f"（覆盖 {report.replaced_rows} 行），耗时 {report.elapsed_ms} ms，状态 {report.status}"
        )
        for warning in report.warnings:
            print(f"  告警：{warning}")

    print(f"Parquet 目录：{settings.parquet_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
