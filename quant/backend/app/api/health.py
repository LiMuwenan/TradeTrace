# -*- coding: utf-8 -*-
"""健康检查：返回服务版本与当前生效的目录，用于确认配置是否正确加载。"""
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request

from app import __version__
from app.schemas import ok

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    settings = request.app.state.settings
    now = datetime.now(ZoneInfo(settings.timezone))
    return ok(
        {
            "status": "ok",
            "version": __version__,
            "timezone": settings.timezone,
            "serverTime": now.isoformat(timespec="seconds"),
            "parquetDir": str(settings.parquet_dir),
            "rawDir": str(settings.raw_dir),
        }
    )
