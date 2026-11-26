# -*- coding: utf-8 -*-
"""通知设置接口（08 号票）：读写配置、发测试通知、查投递记录。

本模块只做参数解析与委派；校验口径在 `app.services.notification_settings`。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.schemas import ok
from app.services import notification_settings as settings_service

router = APIRouter(tags=["settings"])

MAX_PAGE_SIZE = 100


class NotificationConfigUpdate(BaseModel):
    """只传要改的字段；字符串传空串表示清空，凭据不传表示保留原值。"""

    ntfyServer: str | None = None
    ntfyTopic: str | None = None
    ntfyToken: str | None = None
    emailTo: str | None = None
    smtpHost: str | None = None
    smtpPort: int | None = None
    smtpUser: str | None = None
    smtpPassword: str | None = None
    smtpStarttls: bool | None = None
    dailyLimit: int | None = None
    limitEnabled: bool | None = None


@router.get("/settings/notification")
def read_notification_settings(request: Request) -> dict:
    return ok(settings_service.read_config(request.app.state.settings))


@router.put("/settings/notification")
def update_notification_settings(request: Request, payload: NotificationConfigUpdate) -> dict:
    try:
        data = settings_service.update_config(
            request.app.state.settings, payload.model_dump(exclude_unset=True)
        )
    except settings_service.NotifyConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(data)


@router.post("/settings/notification/test")
def test_notification(request: Request) -> dict:
    return ok(settings_service.test_notification(request.app.state.settings))


@router.get("/notifications/log")
def notification_log(
    request: Request,
    date: str | None = None,
    page: int = 1,
    pageSize: int = 20,
) -> dict:
    if page < 1:
        raise HTTPException(status_code=400, detail="page 从 1 开始")
    if not 1 <= pageSize <= MAX_PAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"pageSize 应在 1-{MAX_PAGE_SIZE} 之间")
    data = settings_service.read_logs(
        request.app.state.settings, trade_date=date, page=page, page_size=pageSize
    )
    return ok(data)
