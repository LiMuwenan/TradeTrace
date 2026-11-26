# -*- coding: utf-8 -*-
"""应用工厂：便于测试注入配置，也便于部署时按环境创建实例。"""
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import alerts, data, health, rules, settings as settings_api, stocks, watchlist
from app.config import Settings, load_settings
from app.schemas import fail
from app.services.notify import AlertNotifier, Notifier
from app.storage.stock_names import BaostockNameProvider, StockNameCache
from app.storage.watchlist_store import WatchlistCorruptError

API_PREFIX = "/api/v1"


def create_app(
    settings: Settings | None = None,
    stock_names: StockNameCache | None = None,
    notifier: Notifier | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    _ensure_dirs_writable(settings)

    app = FastAPI(
        title="Quant Platform",
        description="A 股量化数据分析与预警平台（只读行情，不接交易）",
        version=__version__,
    )
    app.state.settings = settings
    app.state.stock_names = stock_names or StockNameCache(
        settings.meta_dir, BaostockNameProvider()
    )
    # 未配置通道时求值仍会落库，只是不投递（ADR 0008）；配置在库里，改完即时生效
    app.state.notifier = notifier or AlertNotifier(settings)

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

    @app.exception_handler(WatchlistCorruptError)
    def handle_watchlist_corrupt(_: Request, exc: WatchlistCorruptError) -> JSONResponse:
        return JSONResponse(status_code=500, content=fail(500, str(exc)))

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(data.router, prefix=API_PREFIX)
    app.include_router(watchlist.router, prefix=API_PREFIX)
    app.include_router(stocks.router, prefix=API_PREFIX)
    app.include_router(rules.router, prefix=API_PREFIX)
    app.include_router(alerts.router, prefix=API_PREFIX)
    app.include_router(settings_api.router, prefix=API_PREFIX)
    return app


def _ensure_dirs_writable(settings: Settings) -> None:
    """启动时验证数据目录可写，避免问题拖到首次写入才暴露。"""
    for label, directory in (
        ("raw_dir", settings.raw_dir),
        ("parquet_dir", settings.parquet_dir),
        ("meta_dir", settings.meta_dir),
    ):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / f".write_probe.{os.getpid()}"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            raise RuntimeError(
                f"{label} 不可写：{directory}；请检查目录权限后重启"
            ) from exc
