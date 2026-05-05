from __future__ import annotations

import smtplib
from email.message import EmailMessage


def _smtp_enabled(app) -> bool:
    host = (app.config.get("SMTP_HOST") or "").strip()
    from_addr = (app.config.get("SMTP_FROM") or "").strip()
    return bool(host and from_addr)


def send_change_email(
    app,
    subscription,
    diff_summary: str,
    *,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "latest_notifications_report.pdf",
) -> tuple[bool, str | None]:
    """
    若有設定 SMTP_*，當訂閱內容變更時寄 email 給使用者。
    subscription 需有：subscription.user.email, subscription.url, subscription.name
    """
    if not _smtp_enabled(app):
        return False, "SMTP 未啟用（請設定 SMTP_HOST 與 SMTP_FROM）"

    to_addr = (getattr(getattr(subscription, "user", None), "email", "") or "").strip()
    if not to_addr:
        return False, "使用者信箱為空"

    host = app.config.get("SMTP_HOST")
    port = int(app.config.get("SMTP_PORT") or 587)
    username = app.config.get("SMTP_USERNAME") or ""
    password = app.config.get("SMTP_PASSWORD") or ""
    from_addr = app.config.get("SMTP_FROM")
    use_tls = bool(app.config.get("SMTP_USE_TLS"))

    sub_name = (subscription.name or "未命名追蹤").strip()
    subject = f"[追蹤更新] {sub_name}"

    body = "\n".join(
        [
            "你的追蹤網站內容有更新：",
            "",
            f"名稱：{sub_name}",
            f"網址：{subscription.url}",
            "",
            "差異摘要：",
            diff_summary or "(無摘要)",
            "",
            "你也可以登入系統點「看差異」查看。",
        ]
    )

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    if pdf_bytes:
        msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)
        return True, None
    except Exception as e:
        # 通知失敗不影響主要流程，但把原因回傳給呼叫端顯示
        return False, f"寄信失敗：{str(e)}"


def send_notifications_report_email(
    app,
    *,
    to_addr: str,
    pdf_bytes: bytes,
    filename: str = "latest_notifications_report.pdf",
) -> tuple[bool, str | None]:
    """Send latest notifications report PDF to user email."""
    if not _smtp_enabled(app):
        return False, "SMTP 未啟用（請設定 SMTP_HOST 與 SMTP_FROM）"

    to_addr = (to_addr or "").strip()
    if not to_addr:
        return False, "使用者信箱為空"

    host = app.config.get("SMTP_HOST")
    port = int(app.config.get("SMTP_PORT") or 587)
    username = app.config.get("SMTP_USERNAME") or ""
    password = app.config.get("SMTP_PASSWORD") or ""
    from_addr = app.config.get("SMTP_FROM")
    use_tls = bool(app.config.get("SMTP_USE_TLS"))

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = "[通知報告] 最新通知 PDF"
    msg.set_content("您好，附件為系統最新通知的 PDF 表格報告。")
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)
        return True, None
    except Exception as e:
        return False, f"寄送通知報告失敗：{str(e)}"

