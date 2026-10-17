"""Outgoing email (sign-in codes). SMTP in production; the "log" provider is for local dev."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutgoingEmail:
    """A plain-text email."""

    to: str
    subject: str
    body: str


# Emails "sent" by the log provider (tests read this; never used in production).
OUTBOX: list[OutgoingEmail] = []


def send_email(message: OutgoingEmail) -> None:
    """Send ``message`` with the configured provider. Failures are logged, not raised.

    Args:
        message: Recipient, subject and body
    """
    if settings.EMAIL_PROVIDER == "log":
        OUTBOX.append(message)
        # Local testing only (production refuses this provider): shows the code in the log.
        logger.warning("[dev email] to=%s subject=%s", message.to, message.subject)
        return
    email = EmailMessage()
    email["From"] = settings.EMAIL_FROM
    email["To"] = message.to
    email["Subject"] = message.subject
    email.set_content(message.body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(email)
    except (OSError, smtplib.SMTPException) as exc:
        logger.error("Could not send email to %s: %s", message.to, type(exc).__name__)


def send_sign_in_code(to: str, code: str) -> None:
    """Email a 6-digit sign-in code (English and Tamil).

    Args:
        to: Recipient email
        code: The one-time code
    """
    minutes = settings.EMAIL_CODE_TTL_MINUTES
    body = "\n".join(
        [
            f"Your Personal Teacher Assistant code is: {code}",
            f"It expires in {minutes} minutes. Do not share it with anyone.",
            "",
            f"உங்கள் Personal Teacher Assistant குறியீடு: {code}",
            f"இது {minutes} நிமிடங்களில் காலாவதியாகும். யாருடனும் பகிர வேண்டாம்.",
            "",
            "If you did not ask for this code, you can ignore this email.",
        ]
    )
    send_email(OutgoingEmail(to=to, subject=f"{code} is your sign-in code", body=body))
