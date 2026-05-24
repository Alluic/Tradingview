from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from tradingview_signal_dashboard.config import SmtpEnvConfig


@dataclass(frozen=True)
class EmailSettings:
    host: str
    port: int
    username: str | None
    password: str | None
    sender: str
    recipient: str
    use_tls: bool


def load_email_settings(config: SmtpEnvConfig) -> EmailSettings:
    host = os.getenv(config.host_env)
    sender = os.getenv(config.from_env)
    recipient = os.getenv(config.to_env)
    if not host or not sender or not recipient:
        missing = [
            name
            for name, value in (
                (config.host_env, host),
                (config.from_env, sender),
                (config.to_env, recipient),
            )
            if not value
        ]
        raise ValueError(f"Missing required email environment variables: {', '.join(missing)}")

    return EmailSettings(
        host=host,
        port=int(os.getenv(config.port_env, "587")),
        username=os.getenv(config.username_env),
        password=os.getenv(config.password_env),
        sender=sender,
        recipient=recipient,
        use_tls=os.getenv(config.use_tls_env, "true").strip().lower() not in {"0", "false", "no"},
    )


def send_email(settings: EmailSettings, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.sender
    message["To"] = settings.recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.host, settings.port, timeout=30) as smtp:
        if settings.use_tls:
            smtp.starttls()
        if settings.username and settings.password:
            smtp.login(settings.username, settings.password)
        smtp.send_message(message)
