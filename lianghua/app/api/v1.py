# -*- coding: utf-8 -*-
"""v1 网关：健康检查。客户端连接测试只用此接口。"""
import datetime

from fastapi import APIRouter

from ..schemas import HealthV1Out

router = APIRouter(prefix="/api/v1", tags=["v1"])


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/health", response_model=HealthV1Out)
def health_v1():
    return HealthV1Out(
        schema_version=1,
        status="ok",
        name="lianghua",
        version="0.1.0",
        server_time=_utc_now(),
    )
