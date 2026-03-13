"""定時檢查所有訂閱的網站是否有更新，有則記錄並可通知。"""
from datetime import datetime
import threading

from backend.models import db, Subscription, Snapshot
from backend.services.scraper import scrape_and_extract, content_hash
from backend.services.diff_service import diff_to_summary


def run_check_subscription(sub_id: int, app):
    """對單一訂閱執行一次檢查（在 app context 內）。"""
    with app.app_context():
        sub = Subscription.query.get(sub_id)
        if not sub:
            return
        try:
            content_text, new_hash = scrape_and_extract(
                sub.url,
                sub.watch_description,
                use_gemini=bool(app.config.get("GEMINI_API_KEY")),
                gemini_api_key=app.config.get("GEMINI_API_KEY", ""),
            )
        except Exception as e:
            # 可記錄失敗日誌，此處僅略過
            return

        last = sub.snapshots[0] if sub.snapshots else None
        now = datetime.utcnow()
        sub.last_checked_at = now

        if last and last.content_hash != new_hash:
            sub.last_changed_at = now
            diff_summary = diff_to_summary(last.content_text or "", content_text)
            # 可在此觸發通知（例如寫入 Notification 表或發送 email）
            snapshot = Snapshot(
                subscription_id=sub.id,
                content_hash=new_hash,
                content_text=content_text[:50000],
                content_full=None,
            )
            db.session.add(snapshot)
        else:
            snapshot = Snapshot(
                subscription_id=sub.id,
                content_hash=new_hash,
                content_text=content_text[:50000],
                content_full=None,
            )
            db.session.add(snapshot)

        sub.last_checked_at = now
        db.session.commit()


def run_all_checks(app):
    """檢查所有訂閱（由排程或手動呼叫）。"""
    with app.app_context():
        ids = [s.id for s in Subscription.query.all()]
    for sub_id in ids:
        try:
            run_check_subscription(sub_id, app)
        except Exception:
            pass


def init_scheduler(app):
    """啟動背景排程：每 N 分鐘檢查一次所有訂閱。"""
    interval_minutes = app.config.get("CHECK_INTERVAL_MINUTES", 30)

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
