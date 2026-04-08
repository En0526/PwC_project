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
        now = datetime.utcnow()
        try:
            content_text, new_hash = scrape_and_extract(
                sub.url,
                sub.watch_description,
                use_gemini=bool(app.config.get("GEMINI_API_KEY")),
                gemini_api_key=app.config.get("GEMINI_API_KEY", ""),
            )
        except Exception as e:
            # 抓取失敗：仍然更新 last_checked_at，但不建立 snapshot
            app.logger.warning(f"訂閱 {sub.id} 抓取失敗: {e}")
            sub.last_checked_at = now
            db.session.commit()
            return

        last = sub.snapshots[0] if sub.snapshots else None

        snapshot = Snapshot(
            subscription_id=sub.id,
            content_hash=new_hash,
            content_text=content_text[:50000],
            content_full=None,
        )
        db.session.add(snapshot)

        if last and last.content_hash != new_hash:
            sub.last_changed_at = now
            diff_summary = diff_to_summary(last.content_text or "", content_text)

        sub.last_checked_at = now
        db.session.commit()


def run_all_checks(app):
    """檢查所有訂閱（由排程或手動呼叫）。
    依每個訂閱的 `check_interval_minutes` 決定是否需要執行檢查。"""
    with app.app_context():
        subs = Subscription.query.all()
        for sub in subs:
            if not sub.check_interval_minutes or sub.check_interval_minutes <= 0:
                sub.check_interval_minutes = 30
                db.session.commit()  # 修復舊資料
            need_check = False
            if not sub.last_checked_at:
                need_check = True
            else:
                elapsed = (datetime.utcnow() - sub.last_checked_at).total_seconds()
                if elapsed >= sub.check_interval_minutes * 60:
                    need_check = True
            if need_check:
                try:
                    run_check_subscription(sub.id, app)
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
