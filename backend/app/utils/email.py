"""
Email Utility for WinVinaya MIS
================================
Asynchronous SMTP email dispatching with Jinja2 templating, STARTTLS support,
multipart MIME (HTML + Plain text fallback), and attachment handling.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Any, List, Optional, Tuple

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

# Resolve templates folder relative to backend/app/templates
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_template(template_name: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 HTML email template with standard default context."""
    ctx = {
        "current_year": datetime.now().year,
        "app_name": settings.APP_NAME,
        **context,
    }
    template = jinja_env.get_template(template_name)
    return template.render(**ctx)


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    cc: Optional[List[str]] = None,
    attachments: Optional[List[Tuple[str, bytes]]] = None,
    reply_to: Optional[str] = None,
) -> bool:
    """Sends an asynchronous HTML email via SMTP using aiosmtplib."""
    if not getattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", True):
        logger.info("Email notifications globally disabled via settings. Skipping send to %s", to_email)
        return False

    smtp_host = settings.SMTP_HOST or "s.mail25.info"
    smtp_port = int(settings.SMTP_PORT or 587)
    smtp_user = settings.SMTP_USER or "no-reply@winvinaya.com"
    smtp_password = settings.SMTP_PASSWORD or "Admin##2025@"
    from_email = settings.EMAILS_FROM_EMAIL or "no-reply@winvinaya.com"
    from_name = settings.EMAILS_FROM_NAME or "winvinaya"
    smtp_tls = bool(settings.SMTP_TLS)

    # Plain text conversion as alternative part
    plain_text = re.sub(r"<[^>]+>", " ", html_content)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()

    if attachments:
        message = MIMEMultipart("mixed")
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(plain_text, "plain", "utf-8"))
        alt_part.attach(MIMEText(html_content, "html", "utf-8"))
        message.attach(alt_part)
        for filename, content in attachments:
            part = MIMEApplication(content)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            message.attach(part)
    else:
        message = MIMEMultipart("alternative")
        message.attach(MIMEText(plain_text, "plain", "utf-8"))
        message.attach(MIMEText(html_content, "html", "utf-8"))

    display_from_name = from_name.strip() if from_name else "WinVinaya MIS"
    if display_from_name.lower() == "winvinaya":
        display_from_name = "WinVinaya MIS"

    message["From"] = f"{display_from_name} <{from_email}>"
    message["To"] = to_email
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="winvinaya.com")
    message["Reply-To"] = reply_to or from_email
    message["Auto-Submitted"] = "auto-generated"
    message["X-Mailer"] = "WinVinaya MIS Enterprise Mailer"

    if cc:
        message["Cc"] = ", ".join(cc)

    # Strategy: direct SSL on port 465, STARTTLS on 587/25
    use_tls_strategy = smtp_tls and smtp_port == 465
    start_tls_strategy = smtp_tls and smtp_port != 465

    try:
        pass_hint = f"{smtp_password[:2]}***{smtp_password[-1]}" if len(smtp_password) > 3 else "***"
        logger.info(
            "Connecting to SMTP %s:%d as '%s' (Pass: %s, TLS: %s) to deliver to '%s'",
            smtp_host,
            smtp_port,
            smtp_user,
            pass_hint,
            smtp_tls,
            to_email,
        )

        recipients = [to_email] + (cc or [])
        send_result = await aiosmtplib.send(
            message,
            sender=from_email,
            recipients=recipients,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_password,
            use_tls=use_tls_strategy,
            start_tls=start_tls_strategy,
            timeout=25.0,
        )
        # aiosmtplib returns (per-recipient refusals, final server response). The
        # server response contains the relay's queue ID, which is what the mail
        # provider needs to trace a message that was accepted but never delivered.
        refused, server_response = send_result
        if refused:
            logger.error("SMTP relay refused recipients for '%s': %s", subject, refused)
            return False
        logger.info(
            "Email '%s' accepted by relay for %s (Message-ID: %s, relay response: %s)",
            subject,
            to_email,
            message["Message-ID"],
            server_response,
        )
        return True

    except aiosmtplib.SMTPAuthenticationError as e:
        logger.error("SMTP Authentication failure for %s at %s: %s", smtp_user, smtp_host, e)
        return False
    except aiosmtplib.SMTPConnectError as e:
        logger.error("SMTP Connection failed to %s:%d: %s", smtp_host, smtp_port, e)
        return False
    except Exception as e:
        logger.error("Error sending email to %s: %s", to_email, str(e), exc_info=True)
        return False


async def verify_smtp_connection() -> dict[str, Any]:
    """Tests the SMTP connection and returns diagnostic status."""
    smtp_host = settings.SMTP_HOST or "s.mail25.info"
    smtp_port = int(settings.SMTP_PORT or 587)
    smtp_user = settings.SMTP_USER or "no-reply@winvinaya.com"
    smtp_password = settings.SMTP_PASSWORD or "Admin##2025@"
    smtp_tls = bool(settings.SMTP_TLS)

    use_tls_strategy = smtp_tls and smtp_port == 465
    start_tls_strategy = smtp_tls and smtp_port != 465

    try:
        smtp = aiosmtplib.SMTP(
            hostname=smtp_host,
            port=smtp_port,
            use_tls=use_tls_strategy,
            start_tls=start_tls_strategy,
            timeout=15.0,
        )
        await smtp.connect()
        if smtp_user and smtp_password:
            await smtp.login(smtp_user, smtp_password)
        await smtp.quit()
        return {
            "success": True,
            "message": f"Successfully connected and authenticated with {smtp_host}:{smtp_port}",
            "host": smtp_host,
            "port": smtp_port,
            "user": smtp_user,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"SMTP verification failed: {str(e)}",
            "host": smtp_host,
            "port": smtp_port,
            "user": smtp_user,
        }
