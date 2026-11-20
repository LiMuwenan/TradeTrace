# -*- coding: utf-8 -*-
"""应用工厂：便于测试注入配置，也便于部署时按环境创建实例。"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import data, health
from app.config import Settings, load_settings
from app.schemas import fail

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    app = FastAPI(
        title="Quant Platform",
        description="A 股量化数据分析与预警平台（只读行情，不接交易）",
        version=__version__,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # 错误体统一为 {code, message}，不把 FastAPI 默认的 {detail} 漏给前端
    @app.exception_handler(StarletteHTTPException)
    def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=fail(exc.status_code, str(exc.detail)))

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content=fail(422, "请求参数不合法"))

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(data.router, prefix=API_PREFIX)
    return app
