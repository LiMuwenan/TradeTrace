# -*- coding: utf-8 -*-
"""v1 接口统一错误体：{ code, message, detail }。既有 /api/* 接口不受影响。"""
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("app.errors")


class ApiError(Exception):
    """业务错误：code 供客户端分支，message 可直接展示，detail 仅调试用。"""

    def __init__(self, status_code: int, code: str, message: str, detail=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    # 只记录路径，不记录本地绝对路径与文件细节
    logger.info("v1 错误 %s %s -> %s", request.method, request.url.path, exc.code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "detail": exc.detail},
    )
