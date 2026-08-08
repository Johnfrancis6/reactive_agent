
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from langchain_core.tools import tool
from app.core.config import get_settings
from app.core.logging import get_logger
import re

log = get_logger(__name__)
settings = get_settings()
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")



def _send_smtp(to: str, subject: str, body: str, cc: str) -> None:
    """Synchronous SMTP execution — called from run_in_executor."""
    if not _EMAIL_RE.match(to):
        raise ValueError(f"Invalid email address: {to!r}")
    if cc and not _EMAIL_RE.match(cc):
        raise ValueError(f"Invalid CC address: {cc!r}")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.smtp_from_email
    msg["To"]      = to
    if cc:
        msg["Cc"] = cc
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
        server.login(settings.smtp_user, settings.smtp_password)
        recipients = [to] + ([cc] if cc else [])
        server.sendmail(settings.smtp_from_email, recipients, msg.as_string())


@tool
async def send_email(to: str, subject: str, body: str, cc: str = "") -> str:
    """
    Send an email.
    IMPORTANT: use this tool only after user confirmation (requires human-in-the-loop).
    """
    try:
        loop = asyncio.get_running_loop()  
        await loop.run_in_executor(None, _send_smtp, to, subject, body, cc)
        log.info("email_sent: to=%s subject=%s", to, subject[:50])
        return f"Email sent successfully to {to} — subject: {subject}"
    except smtplib.SMTPAuthenticationError:
        log.error("email_auth_error: smtp_user=%s", settings.smtp_user)
        return "SMTP authentication error — verify credentials"
    except Exception as e:
        log.error("email_send_error: type=%s error=%s", type(e).__name__, e)
        return f"Error sending email: {type(e).__name__}"