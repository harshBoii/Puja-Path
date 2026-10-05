"""Ops alerts by email and Slack (SLA breaches, reconciliation mismatches). Never fails silently: logs always."""

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import urlparse

import httpx

from config import settings
from logging_setup import log

logger = logging.getLogger("alerts")


async def ops_alert(subject: str, text: str, **ctx) -> None:
    log(logger, f"OPS ALERT: {subject}", text=text, **ctx)
    if settings.slack_webhook_url:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(settings.slack_webhook_url, json={"text": f"*{subject}*\n{text}"})
        except Exception as e:  # noqa: BLE001
            logger.error("slack alert failed: %s", e)
    if settings.smtp_url and settings.ops_alert_email:
        try:
            u = urlparse(settings.smtp_url)  # smtp://user:pass@host:587
            msg = EmailMessage()
            msg["Subject"] = f"[{settings.brand} ops] {subject}"
            msg["From"] = u.username or settings.ops_alert_email
            msg["To"] = settings.ops_alert_email
            msg.set_content(text)
            with smtplib.SMTP(u.hostname, u.port or 587, timeout=10) as s:
                s.starttls()
                if u.username:
                    s.login(u.username, u.password or "")
                s.send_message(msg)
        except Exception as e:  # noqa: BLE001
            logger.error("email alert failed: %s", e)
    from providers.recorder import record

    if settings.is_dev:
        await record("alerts", "ops_alert", {"subject": subject, "text": text, **{k: str(v) for k, v in ctx.items()}})
