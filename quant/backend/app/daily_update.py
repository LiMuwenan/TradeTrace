# -*- coding: utf-8 -*-
"""每日增量入库命令：

    python -m app.daily_update [YYYY-MM-DD]

不指定日期时取配置时区的“今天”。走 `RealtimeSource` + `Ingestor.ingest_day`，
与历史导入共用唯一写入口；抓到的原始 CSV 会按历史目录格式归档到 `data.raw_dir`。
股票入库完成后，再补一次自选指数的增量（另一套单只接口，见 `index_quotes`）。
"""
from __future__ import annotations

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import load_settings
from app.services import index_quotes
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

    # 指数单独取数（单只按区间），失败只提示，不影响已完成的股票入库
    index_report = index_quotes.sync_watchlist(settings, trade_date)
    print(
        f"  指数：{len(index_report['touched'])} 只更新 {index_report['rows']} 行"
        + (f"，{len(index_report['errors'])} 只失败" if index_report["errors"] else "")
    )
    for error in index_report["errors"]:
        print(f"    失败：{error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
