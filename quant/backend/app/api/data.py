# -*- coding: utf-8 -*-
"""数据层接口：数据状态与按标的读取逐日序列。"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ok
from app.services.data_status import build_status
from app.storage.parquet_store import ParquetStore
from app.storage.schema import IngestError, normalize_code

router = APIRouter(tags=["data"])


@router.get("/data/status")
def data_status(request: Request) -> dict:
    return ok(build_status(request.app.state.settings))


@router.get("/data/series")
def data_series(
    request: Request,
    code: str,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    try:
        normalized = normalize_code(code)
    except IngestError as exc:
        raise HTTPException(status_code=400, detail="标的代码格式应为 sh.600000 / sz.000001") from exc
    start = _valid_date(start, "start")
    end = _valid_date(end, "end")
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="start 不能晚于 end")

    items = ParquetStore(request.app.state.settings.parquet_dir).series(normalized, start, end)
    return ok({"code": normalized, "count": len(items), "items": items})


def _valid_date(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field} 应为 YYYY-MM-DD") from exc
