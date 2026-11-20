# -*- coding: utf-8 -*-
"""每日增量入库命令：

    python -m app.daily_update [YYYY-MM-DD]

不指定日期时取配置时区的“今天”。走 `RealtimeSource` + `Ingestor.ingest_day`，
与历史导入共用唯一写入口；抓到的原始 CSV 会按历史目录格式归档到 `data.raw_dir`。
"""
from __future__ import annotations

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import load_settings
from app.storage.ingest import Ingestor
from app.storage.schema import IngestError
from app.storage.sources import BaostockFetcher, RealtimeSource


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取并入库某一交易日的全市场日 K")
    parser.add_argument("trade_date", nargs="?", help="交易日 YYYY-MM-DD，默认今天")
    args = parser.parse_args(argv)

    settings = load_settings()
    trade_date = args.trade_date or datetime.now(ZoneInfo(settings.timezone)).date().isoformat()

    try:
        source = RealtimeSource(BaostockFetcher(), settings.raw_dir)
        report = Ingestor(settings).ingest_day(trade_date, source)
    except IngestError as exc:
        print(f"{trade_date} 入库失败：{exc}")
        return 1

    print(
        f"{trade_date}：来源 {report.source}，写入 {report.rows} 行"
        f"（覆盖 {report.replaced_rows} 行），耗时 {report.elapsed_ms} ms，状态 {report.status}"
    )
    for warning in report.warnings:
        print(f"  告警：{warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
