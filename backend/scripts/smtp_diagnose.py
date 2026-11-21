"""
SMTP delivery diagnostic.

Sends two test messages through the configured relay and prints the full SMTP
conversation, so you can see exactly what the relay answers (incl. queue ID):
  1. a minimal plain-text email (no links, no HTML)
  2. the real invitation template

Usage (from the backend folder, with the venv active):
    python scripts/smtp_diagnose.py you@gmail.com
"""
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.utils.email import render_template  # noqa: E402


def build(to_addr: str, subject: str, text: str, html: str | None = None):
    if html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
    else:
        msg = MIMEText(text, "plain", "utf-8")
    msg["From"] = f"WinVinaya MIS <{settings.EMAILS_FROM_EMAIL}>"
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="winvinaya.com")
    return msg


def send(msg, to_addr: str):
    print(f"\n===== Sending: {msg['Subject']} =====")
    with smtplib.SMTP(settings.SMTP_HOST, int(settings.SMTP_PORT), timeout=30) as s:
        s.set_debuglevel(1)
        s.ehlo()
        if settings.SMTP_TLS and int(settings.SMTP_PORT) != 465:
            s.starttls()
            s.ehlo()
        s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        refused = s.send_message(msg, from_addr=settings.EMAILS_FROM_EMAIL, to_addrs=[to_addr])
        print("Refused recipients:", refused or "none")
        print("Message-ID:", msg["Message-ID"])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    to_addr = sys.argv[1]

    send(build(to_addr, "WVISMIS SMTP test 1 (plain text)",
               "This is a plain-text delivery test from WinVinaya MIS."), to_addr)

    url = "https://dev-mis.winvinaya.com/auth/accept-invite?token=diagnostic-test"
    html = render_template("user_invite.html", {
        "org_name": "WinVinaya InfoSystems",
        "inviter_name": "SMTP Diagnostic",
        "user_name": "Tester",
        "invite_url": url,
    })
    send(build(to_addr, "WVISMIS SMTP test 2 (invite template)",
               f"You have been invited to WinVinaya MIS. Accept: {url}", html), to_addr)


if __name__ == "__main__":
    main()
