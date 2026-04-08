"""定時檢查所有訂閱的網站是否有更新，有則記錄並可通知。"""
from datetime import datetime
import threading

from backend.models import db, Subscription, Snapshot
from backend.services.scraper import scrape_and_extract
from backend.services.diff_service import diff_to_summary
from backend.services.email_service import send_change_email
from backend.services.blocked_sites import looks_like_anti_bot, record_blocked_site


def run_check_subscription(sub_id: int, app) -> tuple[bool, str | None, bool, bool | None, str | None]:
    """
    對單一訂閱執行一次檢查（在 app context 內）。
    回傳 (成功與否, 失敗原因)；抓取失敗仍會更新 last_checked_at，讓前端知道「有按過檢查」。
    """
    with app.app_context():
        sub = Subscription.query.get(sub_id)
        if not sub:
            return False, "找不到訂閱", False, None, None
        now = datetime.utcnow()
        try:
            content_text, new_hash = scrape_and_extract(
                sub.url,
                sub.watch_description,
                use_gemini=bool(app.config.get("GEMINI_API_KEY")),
                gemini_api_key=app.config.get("GEMINI_API_KEY", ""),
            )
        except Exception as e:
            sub.last_checked_at = now
            db.session.commit()
            err = str(e)
            if looks_like_anti_bot(err):
                record_blocked_site(app, sub.url, err)
            return False, err, False, None, None

        last = sub.snapshots[0] if sub.snapshots else None
        sub.last_checked_at = now

        changed = bool(last and last.content_hash != new_hash)
        mail_sent: bool | None = None
        mail_error: str | None = None

        if changed:
            sub.last_changed_at = now
            diff_summary = diff_to_summary(last.content_text or "", content_text)
            mail_sent, mail_error = send_change_email(app, sub, diff_summary)

        snapshot = Snapshot(
            subscription_id=sub.id,
            content_hash=new_hash,
            content_text=content_text[:50000],
            content_full=None,
        )
        db.session.add(snapshot)

        db.session.commit()
        return True, None, changed, mail_sent, mail_error


def run_all_checks(app):
    """檢查所有訂閱（由排程或手動呼叫）。"""
    now = datetime.utcnow()
    with app.app_context():
        subs = Subscription.query.all()
        due_ids: list[int] = []
        for s in subs:
            interval = s.check_interval_minutes or 30
            if not s.last_checked_at:
                due_ids.append(s.id)
                continue
            delta = now - s.last_checked_at
            if delta.total_seconds() >= interval * 60:
                due_ids.append(s.id)

    for sub_id in due_ids:
        try:
            run_check_subscription(sub_id, app)
        except Exception:
            pass


def init_scheduler(app):
    """啟動背景排程：每 N 分鐘檢查一次所有訂閱。"""
    interval_minutes = max(1, int(app.config.get("CHECK_INTERVAL_MINUTES", 30)))

    def job():
        run_all_checks(app)

    def run_schedule():
        import schedule
        import time
        schedule.every(interval_minutes).minutes.do(job)
        job()  # 啟動時先跑一次
        while True:
            schedule.run_pending()
            time.sleep(60)

    t = threading.Thread(target=run_schedule, daemon=True)
    t.start()
