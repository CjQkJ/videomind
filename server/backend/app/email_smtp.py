import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.config import get_settings

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "email_code.html"


def render_email_code_html(
    recipient_name: str,
    code: str,
    expires_in_minutes: int,
    site_name: str,
) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    return (
        html.replace("{{recipient_name}}", recipient_name)
        .replace("{{verification_code}}", code)
        .replace("{{expires_in_minutes}}", str(expires_in_minutes))
        .replace("{{site_name}}", site_name)
    )


def send_verification_email(to_email: str, code: str) -> None:
    s = get_settings()
    if not s.smtp_user or not s.smtp_password:
        raise RuntimeError("SMTP 未配置：请设置 SMTP_USER / SMTP_PASSWORD")

    html = render_email_code_html(
        recipient_name=to_email.split("@")[0],
        code=code,
        expires_in_minutes=s.email_code_expire_minutes,
        site_name=s.site_name,
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{s.site_name}] 邮箱验证码"
    from_email = s.smtp_from_email or s.smtp_user
    msg["From"] = f"{s.smtp_from_name} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=context, timeout=30) as server:
        server.login(s.smtp_user, s.smtp_password)
        server.sendmail(from_email, [to_email], msg.as_string())
