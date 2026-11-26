# -*- coding: utf-8 -*-
"""收盘后定时触发（10 号票）。

不引 cron，也不加调度框架：服务本身就是长期运行的局域网进程，进程内一个 asyncio
任务足够，少一个部署依赖。到点后把同步流水线丢进线程执行，不阻塞 API 请求。

重启后内存里的「今天已跑过」会丢，当天可能再跑一次——流水线本身幂等，重复执行
不会产生重复预警，也不会改写已投递的日报。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

from app.config import Settings

logger = logging.getLogger(__name__)

TICK_SECONDS = 30


class DailyScheduler:
    def __init__(
        self,
        settings: Settings,
        *,
        notifier=None,
        runner: Callable[..., dict] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.notifier = notifier
        self._runner = runner
        self._clock = clock or (lambda: datetime.now(ZoneInfo(settings.timezone)))
        self._last_triggered: str | None = None
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def due(self) -> str | None:
        """到点且今天还没跑过就返回交易日，否则 None。周末直接跳过。"""
        now = self._clock()
        if now.weekday() >= 5:
            return None
        if now.strftime("%H:%M") < self.settings.schedule_time:
            return None
        today = now.date().isoformat()
        if self._last_triggered == today:
            return None
        return today

    def tick(self) -> dict | None:
        """同步执行一次判定；返回流水线结果，未到点返回 None。"""
        today = self.due()
        return None if today is None else self._execute(today)

    def _execute(self, today: str) -> dict:
        # 先标记再执行：失败也计为「今天已触发」，避免每 30 秒重试打爆数据源；
        # 失败会留下 failed 运行记录，由次日补跑覆盖。
        self._last_triggered = today
        runner = self._runner
        if runner is None:
            from app.services import pipeline

            runner = pipeline.scheduled_run
        return runner(self.settings, today, notifier=self.notifier)

    async def serve(self) -> None:
        while not self._stopped:
            today = self.due()
            if today is not None:
                try:
                    # 流水线是同步的，放线程里跑，别把事件循环堵住
                    await asyncio.to_thread(self._execute, today)
                except Exception as exc:  # 定时任务失败不能把服务带崩
                    logger.exception("收盘流水线执行失败：%s", exc)
            await asyncio.sleep(TICK_SECONDS)
