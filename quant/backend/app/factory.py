# -*- coding: utf-8 -*-
"""应用工厂：便于测试注入配置，也便于部署时按环境创建实例。"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import alerts, data, health, pipeline, reports, rules, settings as settings_api, stocks, watchlist
from app.config import PROJECT_ROOT, Settings, load_settings
from app.schemas import fail
from app.services.notify import AlertNotifier, Notifier
from app.services.scheduler import DailyScheduler
from app.storage.stock_names import BaostockNameProvider, StockNameCache
from app.storage.watchlist_store import WatchlistCorruptError

API_PREFIX = "/api/v1"

# 前端构建产物；存在就由后端一并托管，容器里只有这一个进程
WEB_DIST = PROJECT_ROOT / "web" / "dist"


def create_app(
    settings: Settings | None = None,
    stock_names: StockNameCache | None = None,
    notifier: Notifier | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    _ensure_dirs_writable(settings)

    scheduler = DailyScheduler(settings) if settings.schedule_enabled else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if scheduler is not None:
            scheduler.notifier = app.state.notifier
            task = asyncio.create_task(scheduler.serve())
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.stop()
            if task is not None:
                task.cancel()

    app = FastAPI(
        title="Quant Platform",
        description="A 股量化数据分析与预警平台（只读行情，不接交易）",
        version=__version__,
        lifespan=lifespan,
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
    app.include_router(reports.router, prefix=API_PREFIX)
    app.include_router(pipeline.router, prefix=API_PREFIX)
    app.include_router(settings_api.router, prefix=API_PREFIX)
    _serve_web(app)
    return app


def _serve_web(app: FastAPI) -> None:
    """有前端构建产物时由后端托管；没有（开发时用 Vite）就保持纯 API。"""
    index = WEB_DIST / "index.html"
    if not index.is_file():
        return

    assets = WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

    root = WEB_DIST.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str):
        # 未命中的接口仍要拿统一 JSON 错误，不能被前端页面接管
        if path == "api" or path.startswith("api/"):
            raise StarletteHTTPException(status_code=404, detail="Not Found")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        # 其余路径交给前端路由（vue-router history 模式刷新/直链都能进）
        return FileResponse(index)


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
