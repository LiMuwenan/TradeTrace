# -*- coding: utf-8 -*-
"""行情存储：按年份分区的 Parquet 与唯一写入口。

对外只需要 `Ingestor`：所有入库都必须经过它的 `ingest_days` / `ingest_day`，
其他模块不得直接写 Parquet。
"""
from app.storage.ingest import Ingestor, IngestReport
from app.storage.parquet_store import ParquetStore
from app.storage.sources import HistoricalCsvSource, RealtimeSource

__all__ = ["Ingestor", "IngestReport", "ParquetStore", "HistoricalCsvSource", "RealtimeSource"]
