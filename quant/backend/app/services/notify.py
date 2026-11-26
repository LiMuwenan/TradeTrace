# -*- coding: utf-8 -*-
"""通知通道的接口。08 号票实现 ntfy 与邮件，本票只定义签约与占位实现。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PushOutcome:
    ok: bool
    channel: str | None = None
    error: str | None = None


class Notifier(Protocol):
    """一条预警的投递。实现方自行决定用哪个通道。"""

    configured: bool

    def send(self, alert: dict) -> PushOutcome: ...


class NullNotifier:
    """08 上线前的占位实现：不投递，也不标记已推送，预警留在库里等重跑补推。"""

    configured = False

    def send(self, alert: dict) -> PushOutcome:  # pragma: no cover - 占位实现
        return PushOutcome(ok=False, error="通知通道尚未实现（08 号票）")
