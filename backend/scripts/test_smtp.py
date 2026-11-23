"""
Self-contained SMTP Configuration Tester.
Tests SMTP connection, STARTTLS, Authentication, and Message Delivery.
"""
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

# Provided configuration
SMTP_HOST = "s.mail25.info"
SMTP_PORT = 587
SMTP_TLS = True
SMTP_USER = "no-reply@winvinaya.com"
SMTP_PASSWORD = "Testpass123"
EMAILS_FROM_EMAIL = "no-reply@winvinaya.com"
EMAILS_FROM_NAME = "winvinaya"
RECIPIENT = "darandharani6255@gmail.com"


def main():
    to_addr = sys.argv[1] if len(sys.argv) > 1 else RECIPIENT
    print("=" * 60)
    print("SMTP CONFIGURATION TEST")
    print("=" * 60)
    print(f"Host:       {SMTP_HOST}:{SMTP_PORT}")
    print(f"TLS:        {SMTP_TLS}")
    print(f"User:       {SMTP_USER}")
    print(f"From:       {EMAILS_FROM_NAME} <{EMAILS_FROM_EMAIL}>")
    print(f"Recipient:  {to_addr}")
    print("=" * 60)

    # 1. Build email message
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{EMAILS_FROM_NAME} <{EMAILS_FROM_EMAIL}>"
    msg["To"] = to_addr
    msg["Subject"] = "WinVinaya MIS - SMTP Test Email"
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="winvinaya.com")

    text_body = (
        "Hello,\n\n"
        "This is a verification test email from WinVinaya MIS.\n"
        f"SMTP Server: {SMTP_HOST}:{SMTP_PORT}\n"
        "If you received this email, the SMTP configuration is working properly!\n"
    )

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
          <div style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); padding: 20px; text-align: center; color: white;">
            <h2 style="margin: 0;">WinVinaya MIS - SMTP Test</h2>
          </div>
          <div style="padding: 24px; background-color: #ffffff;">
            <p>Hello,</p>
            <p>This is a verification test email from <strong>WinVinaya MIS</strong>.</p>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
              <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">SMTP Host:</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{SMTP_HOST}:{SMTP_PORT}</td>
              </tr>
              <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Sender:</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{EMAILS_FROM_NAME} &lt;{EMAILS_FROM_EMAIL}&gt;</td>
              </tr>
              <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Status:</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; color: #16a34a; font-weight: bold;">✓ Connected & Delivered</td>
              </tr>
            </table>
            <p style="color: #666; font-size: 13px;">If you see this message, your SMTP credentials and delivery path are fully operational.</p>
          </div>
          <div style="background-color: #f9fafb; padding: 12px; text-align: center; font-size: 12px; color: #9ca3af;">
            WinVinaya InfoSystems · Automated Diagnostic
          </div>
        </div>
      </body>
    </html>
    """

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # 2. Connect and deliver
    try:
        print("\n[1/4] Connecting to SMTP server...")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=25)
        server.set_debuglevel(1)

        print("\n[2/4] Sending EHLO...")
        server.ehlo()

        if SMTP_TLS:
            print("\n[3/4] Initiating STARTTLS...")
            server.starttls()
            server.ehlo()

        print("\n[4/4] Authenticating with user credentials...")
        server.login(SMTP_USER, SMTP_PASSWORD)

        print("\n[>] Delivering message...")
        refused = server.send_message(msg, from_addr=EMAILS_FROM_EMAIL, to_addrs=[to_addr])

        if refused:
            print(f"\n[!] Warning: Some recipients were refused: {refused}")
        else:
            print("\n" + "=" * 60)
            print("SUCCESS: Test email accepted by SMTP server for delivery!")
            print(f"Delivered to: {to_addr}")
            print(f"Message ID:   {msg['Message-ID']}")
            print("=" * 60)

        server.quit()

    except smtplib.SMTPAuthenticationError as e:
        print("\n" + "!" * 60)
        print(f"ERROR: SMTP Authentication Failed: {e}")
        print("Please verify SMTP_USER and SMTP_PASSWORD.")
        print("!" * 60)
        sys.exit(1)
    except smtplib.SMTPConnectError as e:
        print("\n" + "!" * 60)
        print(f"ERROR: Could not connect to {SMTP_HOST}:{SMTP_PORT} - {e}")
        print("!" * 60)
        sys.exit(1)
    except Exception as e:
        print("\n" + "!" * 60)
        print(f"ERROR: {type(e).__name__}: {e}")
        print("!" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
