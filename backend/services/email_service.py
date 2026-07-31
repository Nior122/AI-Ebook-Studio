"""Email delivery for auth flows (password reset, email verification).

Sends via SMTP when ``SMTP_HOST`` is configured; otherwise (local dev / no SMTP)
the email is written to the application log with the link, which keeps the
flows fully testable and usable during development.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from core.config import Settings, get_settings

logger = logging.getLogger("api.email")


def _build_mime(subject: str, html: str, to_email: str, settings: Settings) -> MIMEMultipart:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.email_from
    message["To"] = to_email
    message.attach(MIMEText(html, "html", "utf-8"))
    return message


def send_auth_email(to_email: str, subject: str, link: str, settings: Settings | None = None) -> None:
    """Deliver an auth email. SMTP when configured, console log otherwise."""
    resolved: Settings = settings or get_settings()
    html = (
        "<div style='font-family:system-ui,sans-serif;max-width:480px;margin:0 auto'>"
        f"<h2 style='color:#4f46e5'>AI Ebook Studio</h2>"
        f"<p>{subject}.</p>"
        f"<p><a href='{link}' style='display:inline-block;background:#4f46e5;color:#fff;"
        f"padding:10px 18px;border-radius:8px;text-decoration:none'>Open the link</a></p>"
        f"<p style='color:#6b7280;font-size:13px'>Or copy this address into your browser:<br/>"
        f"<code>{link}</code></p>"
        f"<p style='color:#9ca3af;font-size:12px'>If you did not request this email, you can "
        f"ignore it. The link expires automatically.</p>"
        "</div>"
    )
    if resolved.smtp_host:
        try:
            with smtplib.SMTP(resolved.smtp_host, resolved.smtp_port, timeout=15) as server:
                if resolved.smtp_user:
                    server.starttls()
                    server.login(resolved.smtp_user, resolved.smtp_password or "")
                server.sendmail(
                    resolved.email_from,
                    [to_email],
                    _build_mime(subject, html, to_email, resolved).as_string(),
                )
            logger.info("email_sent to=%s subject=%s", to_email, subject)
        except Exception:
            logger.exception("email_send_failed to=%s subject=%s", to_email, subject)
            raise
        return
    logger.info("email_dev_mode to=%s subject=%s link=%s", to_email, subject, link)


def dev_link_message(link: str | None) -> str | None:
    """Prefix for dev-mode messages so the link is discoverable in tests/logs."""
    return f"Dev link: {link}" if link else None
