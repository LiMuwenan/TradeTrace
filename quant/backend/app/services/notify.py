# -*- coding: utf-8 -*-
"""通知通道：ntfy 优先、邮件兜底，并记录每次投递的结果（08 号票）。

口径（08 票 + ADR 0008 / 0009）：
- 只投递预警（`enter`、非回放）；投递失败不抛给求值流程，只记录；
- ntfy 走短超时的出站 HTTP（局域网服务不能接收公网入站），超时即降级邮件；
- 设置页的测试通知不占每日额度（`notification_log.event_id` 为空）。

正文必须自足：手机在外网收到推送时看不到服务端页面，必须能从正文判断是否值得回家查看。
"""
from __future__ import annotations

import logging
import smtplib
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable, Protocol

from app.config import Settings
from app.storage import notify_store
from app.storage.meta_db import connect, now_iso

logger = logging.getLogger(__name__)

NTFY_TIMEOUT = 5.0
SMTP_TIMEOUT = 10.0

DISCLAIMER = "本内容仅为数据分析，不构成投资建议"


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
    """未配置任何通道时的占位实现：不投递，也不标记已推送，预警留在库里等重跑补推。"""

    configured = False

    def send(self, alert: dict) -> PushOutcome:  # pragma: no cover - 占位实现
        return PushOutcome(ok=False, error="通知通道尚未配置")

    def send_report(self, report: dict) -> PushOutcome:  # pragma: no cover - 占位实现
        return PushOutcome(ok=False, error="通知通道尚未配置")


class AlertNotifier:
    """ntfy → 邮件 的降级链，投递结果写 `notification_log`。"""

    def __init__(
        self,
        settings: Settings,
        *,
        ntfy_sender: Callable[[notify_store.NotificationConfig, dict], None] | None = None,
        email_sender: Callable[[notify_store.NotificationConfig, dict], None] | None = None,
    ) -> None:
        self.settings = settings
        self._ntfy_sender = ntfy_sender or post_ntfy
        self._email_sender = email_sender or send_email

    @property
    def configured(self) -> bool:
        return self._config().configured

    def send(self, alert: dict) -> PushOutcome:
        return self._deliver(
            self._config(),
            _alert_payload(alert),
            event_id=alert.get("id"),
            trade_date=str(alert.get("tradeDate") or ""),
        )

    def send_test(self, alert: dict) -> PushOutcome:
        """设置页的测试通知：不占每日额度，但照常记录结果。"""
        return self._deliver(
            self._config(),
            _alert_payload(alert),
            event_id=None,
            trade_date=str(alert.get("tradeDate") or ""),
        )

    def send_report(self, report: dict) -> PushOutcome:
        """日报：走同一条降级链，但不占每日预警额度（它不是一条预警）。"""
        return self._deliver(
            self._config(),
            {"subject": report_subject(report), "text": report_text(report)},
            event_id=None,
            trade_date=str(report.get("tradeDate") or ""),
        )

    def _deliver(
        self,
        config: notify_store.NotificationConfig,
        payload: dict,
        *,
        event_id: int | None,
        trade_date: str,
    ) -> PushOutcome:
        errors: list[str] = []
        if config.ntfy_ready:
            try:
                self._ntfy_sender(config, payload)
                self._log(trade_date, event_id, "ntfy", notify_store.RESULT_OK, None)
                return PushOutcome(ok=True, channel="ntfy")
            except Exception as exc:  # 网络、超时、鉴权失败一律降级
                logger.warning("ntfy 推送失败，尝试邮件兜底：%s", exc)
                errors.append(f"ntfy：{exc}")

        if config.email_ready:
            try:
                self._email_sender(config, payload)
                result = notify_store.RESULT_FALLBACK if errors else notify_store.RESULT_OK
                self._log(trade_date, event_id, "email", result, "；".join(errors) or None)
                return PushOutcome(ok=True, channel="email")
            except Exception as exc:
                logger.warning("邮件发送失败：%s", exc)
                errors.append(f"邮件：{exc}")

        detail = "；".join(errors) or "未配置任何通知通道"
        self._log(trade_date, event_id, None, notify_store.RESULT_FAILED, detail)
        return PushOutcome(ok=False, error=detail)

    def _config(self) -> notify_store.NotificationConfig:
        conn = connect(self.settings.meta_dir, self.settings.timezone)
        try:
            return notify_store.load_config(conn)
        finally:
            conn.close()

    def _log(
        self,
        trade_date: str,
        event_id: int | None,
        channel: str | None,
        result: str,
        detail: str | None,
    ) -> None:
        try:
            conn = connect(self.settings.meta_dir, self.settings.timezone)
            try:
                notify_store.log_attempt(
                    conn,
                    event_id=event_id,
                    trade_date=trade_date,
                    channel=channel,
                    result=result,
                    detail=detail,
                    timezone=self.settings.timezone,
                )
            finally:
                conn.close()
        except Exception as exc:  # 记录失败不能反过来把一次成功投递变成异常
            logger.warning("投递记录写入失败：%s", exc)


def alert_title(alert: dict) -> str:
    name = str(alert.get("name") or "").strip()
    head = f"{alert.get('code', '')} {name}".strip()
    return f"{head} {alert.get('ruleName') or ''} 触发".strip()


def alert_text(alert: dict) -> str:
    """推送正文。纯文本、不依赖 Markdown 渲染，任何阅读器里都能读。"""
    lines = [
        alert_title(alert),
        "",
        f"指标：{_metric_line(alert)}",
        f"判定价：{_number(alert.get('price'))}（后复权）",
        f"数据日期：{alert.get('tradeDate') or '—'}",
        "",
        DISCLAIMER,
    ]
    return "\n".join(lines)


def _metric_line(alert: dict) -> str:
    rule_type = str(alert.get("ruleType") or "")
    value = _number(alert.get("value"))
    threshold = _number(alert.get("threshold"))
    window = alert.get("window")
    if rule_type == "oversold":
        return f"回落 {value}%（阈值 {threshold}%）"
    if rule_type in ("volume_surge", "volume_shrink"):
        return f"量比 {value}（阈值 {threshold}）"
    if rule_type == "ma_cross":
        return f"均线 {value}（前 {window} 日）" if window else f"均线 {value}"
    if rule_type == "breakout":
        return f"前 {window} 日最高 {value}" if window else f"区间最高 {value}"
    return f"触发值 {value}"


def _number(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def build_test_alert(settings: Settings) -> dict:
    """设置页测试通知的内容，形状与真实预警一致，便于一次验证排版。"""
    return {
        "id": None,
        "code": "sh.600000",
        "name": "测试标的",
        "ruleId": 0,
        "ruleType": "breakout",
        "ruleName": "测试通知",
        "value": 12.34,
        "threshold": None,
        "price": 12.56,
        "window": 60,
        "tradeDate": now_iso(settings.timezone)[:10],
    }


def _alert_payload(alert: dict) -> dict:
    """通道收到的最小投递单元：标题 + 正文。日报与预警共用它。"""
    return {"subject": alert_title(alert), "text": alert_text(alert)}


def report_subject(report: dict) -> str:
    triggers = report.get("triggers") or []
    return f"{report.get('tradeDate') or ''} 收盘日报（{len(triggers)} 条触发）".strip()


def report_text(report: dict) -> str:
    """日报正文。手机上看不到 Web，所以「今天到底有没有事」必须一眼能读到。"""
    triggers = report.get("triggers") or []
    near = report.get("nearMisses") or []
    summary = report.get("watchlistSummary") or {}

    lines = [
        report_subject(report),
        "",
        f"数据日期：{report.get('dataDate') or report.get('tradeDate') or '—'}",
        "",
        f"触发（{len(triggers)} 条）",
    ]
    lines.extend(_report_items(triggers))
    lines.extend(["", f"接近阈值（{len(near)} 条）"])
    lines.extend(_report_items(near))
    lines.extend(
        [
            "",
            f"自选涨跌：{summary.get('total', 0)} 只，"
            f"涨 {summary.get('up', 0)} / 跌 {summary.get('down', 0)} / 平 {summary.get('flat', 0)}",
        ]
    )
    if summary.get("suspended"):
        lines.append(f"其中停牌 {summary['suspended']} 只")
    lines.extend(["", DISCLAIMER])
    return "\n".join(lines)


REPORT_MAX_ITEMS = 20


def _report_items(items: list[dict]) -> list[str]:
    if not items:
        return ["- 无"]
    lines = [f"- {_trigger_line(item)}" for item in items[:REPORT_MAX_ITEMS]]
    if len(items) > REPORT_MAX_ITEMS:
        lines.append(f"- 另有 {len(items) - REPORT_MAX_ITEMS} 条，见 Web 日报")
    return lines


def _trigger_line(item: dict) -> str:
    head = f"{item.get('code', '')} {item.get('name') or ''}".strip()
    return f"{head} · {item.get('ruleName') or ''} · {_metric_line(item)}"


def post_ntfy(config: notify_store.NotificationConfig, payload: dict) -> None:
    """出站 HTTP 推送。超时必须短：一次网络抖动不能拖死整个求值请求。"""
    topic = urllib.parse.quote(str(config.ntfy_topic or ""), safe="")
    url = f"{config.ntfy_server.rstrip('/')}/{topic}"
    request = urllib.request.Request(url, data=payload["text"].encode("utf-8"), method="POST")
    if config.ntfy_token:
        request.add_header("Authorization", f"Bearer {config.ntfy_token}")
    # 标题不放进 HTTP 头：头部按 latin-1 编码，中文会乱码；正文本身已自足
    with urllib.request.urlopen(request, timeout=NTFY_TIMEOUT) as response:
        status = getattr(response, "status", 200)
        if not 200 <= status < 300:
            raise RuntimeError(f"ntfy 返回 HTTP {status}")


def send_email(config: notify_store.NotificationConfig, payload: dict) -> None:
    message = EmailMessage()
    message["Subject"] = payload["subject"]
    message["From"] = config.smtp_user or str(config.email_to)
    message["To"] = str(config.email_to)
    message.set_content(payload["text"])

    with smtplib.SMTP(
        str(config.smtp_host), int(config.smtp_port or 25), timeout=SMTP_TIMEOUT
    ) as smtp:
        if config.smtp_starttls:
            smtp.starttls()
        if config.smtp_user and config.smtp_password:
            smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(message)
