"""
Email service — использует stdlib smtplib через asyncio.to_thread.
Если SMTP_HOST не задан, выводит ссылку в консоль (dev-режим).
"""
import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def _send_smtp(to_email: str, subject: str, html_body: str) -> None:
    """Синхронная отправка — вызывается через asyncio.to_thread."""
    if not settings.SMTP_HOST:
        print(f"[EMAIL] SMTP не настроен. Письмо НЕ отправлено.")
        print(f"[EMAIL] To={to_email} | Subject={subject}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.ehlo()
        if settings.SMTP_TLS:
            smtp.starttls()
            smtp.ehlo()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.sendmail(settings.SMTP_FROM, [to_email], msg.as_bytes())


async def send_invitation_email(to_email: str, role: str, invite_url: str) -> None:
    """Отправить приглашение на email (async). Не бросает исключение при ошибке."""
    role_label = "администратора школы" if role == "school_admin" else "учителя"
    subject = "Приглашение в систему Антиплагиат"
    html_body = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:sans-serif;">
  <div style="max-width:480px;margin:40px auto;background:#fff;border:1px solid #e5e7eb;
              border-radius:12px;padding:32px;">
    <h2 style="margin:0 0 8px;font-size:20px;color:#111827;">Приглашение в Антиплагиат</h2>
    <p style="color:#6b7280;margin:0 0 24px;font-size:14px;">
      Вы приглашены в систему в роли <strong style="color:#374151;">{role_label}</strong>.
    </p>
    <a href="{invite_url}"
       style="display:inline-block;background:#2563eb;color:#fff;padding:12px 28px;
              border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
      Принять приглашение
    </a>
    <p style="margin:24px 0 0;font-size:12px;color:#9ca3af;">
      Ссылка действует 7 дней. Если вы не ожидали это письмо — просто проигнорируйте его.
    </p>
    <hr style="border:none;border-top:1px solid #f3f4f6;margin:24px 0 16px;">
    <p style="margin:0;font-size:11px;color:#d1d5db;">
      Antiplagiat &middot; <a href="{settings.FRONTEND_URL}" style="color:#d1d5db;">{settings.FRONTEND_URL}</a>
    </p>
  </div>
</body>
</html>"""
    try:
        await asyncio.to_thread(_send_smtp, to_email, subject, html_body)
    except Exception as exc:
        # Не прерываем основной флоу — просто логируем
        print(f"[EMAIL] Ошибка отправки на {to_email}: {exc}")
        print(f"[EMAIL] Ссылка для приглашения: {invite_url}")
