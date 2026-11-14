"""Outgoing email over SMTP, using only the standard library.

Configured through SMTP_* settings (see backend/.env.example). Any SMTP
account works, including free ones, so no paid email service is required.
When SMTP is not configured, `is_configured()` is False and callers must
tell the user the feature is unavailable rather than pretend a message
was sent.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 15


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def send_email(to_address: str, subject: str, body: str) -> None:
    """Sends a plain-text email. Synchronous: call via run_in_threadpool.
    Raises on failure so the caller can decide what to tell the user."""
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    if settings.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS, context=context
        ) as server:
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as server:
            server.starttls(context=context)
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
