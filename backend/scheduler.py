"""定時檢查所有訂閱的網站是否有更新，有則記錄並可通知。"""
from datetime import datetime
import threading

from backend.models import db, Subscription, Snapshot, Notification
from backend.services.scraper import scrape_and_extract, ScrapeFailure
from backend.services.diff_service import diff_to_summary
from backend.services.stdtime_notify import stdtime_diff_summary
from backend.services.email_service import send_change_email
from backend.services.blocked_sites import looks_like_anti_bot, record_blocked_site
from backend.services.gazette_monitor_agent import is_gazette_url
from backend.services.gazette_diff_agent import generate_gazette_visual_report

STDTIME_CHECK_INTERVAL_SECONDS = 30


def _is_meaningful_change(old_content: str, new_content: str) -> bool:
    """
    判斷內容變化是否具有意義。
    目前所有內容變化都會當成有意義，包含時間更新。
    """
    if not old_content or not new_content:
        return True

    from backend.services.diff_service import compute_diff
    diffs = compute_diff(old_content, new_content)
    return any(op != 0 for op, text in diffs)



def run_check_subscription(sub_id: int, app) -> tuple[bool, str | None, bool, bool | None, str | None, dict]:
    """
    對單一訂閱執行一次檢查（在 app context 內）。
    回傳 (成功與否, 失敗原因)；抓取失敗仍會更新 last_checked_at，讓前端知道「有按過檢查」。
    
    返回診斷代碼：
      - 反爬類型: http_403, http_429, http_error, rss_fetch_failed_blocked, rss_fetch_failed_timeout
      - 無 RSS 類型: rss_not_found, rss_parse_failed
      - 動態頁面類型: html_dynamic_unreadable
      - 其他: timeout, connection_error, ssl_error 等
    """
    with app.app_context():
        sub = Subscription.query.get(sub_id)
        if not sub:
            return False, "找不到訂閱", False, None, None
        now = datetime.utcnow()
        try:
            content_text, new_hash, scrape_meta = scrape_and_extract(
                sub.url,
                sub.watch_description,
                use_gemini=bool(app.config.get("GEMINI_API_KEY")),
                gemini_api_key=app.config.get("GEMINI_API_KEY", ""),
            )
        except ScrapeFailure as e:
            sub.last_checked_at = now
            db.session.commit()
            err = str(e)
            
            # 記錄反爬阻擋（包括 RSS 源被阻擋的情況）
            if e.code in ("http_403", "http_429", "rss_fetch_failed_blocked") or looks_like_anti_bot(err):
                record_blocked_site(app, sub.url, f"{e.code}: {err}")
            
            # 為不同的失敗類型生成更詳細的 hint
            hint = e.hint  # 預設使用 scraper 提供的 hint
            
            # 針對 RSS-related 的失敗，提供額外提示
            if e.code == "rss_not_found":
                hint = f"❌ 此 URL 不提供 RSS feed（返回 HTML 或錯誤頁）。{hint}"
            elif e.code == "rss_fetch_failed_blocked":
                hint = f"⚠️ 反爬阻擋：RSS 源返回 403/429。{hint}"
            elif e.code == "rss_fetch_failed_timeout":
                hint = f"⏱️ 超時：無法連線到 RSS 源。{hint}"
            elif e.code == "rss_fetch_failed":
                hint = f"❌ 無法取得 RSS：{hint}"
            elif e.code == "http_403":
                hint = f"⚠️ 反爬阻擋（403）：此網站拒絕自動訪問。{hint}"
            elif e.code == "http_429":
                hint = f"⏱️ 被限流（429）：請求過於頻繁。{hint}"
            elif e.code == "html_dynamic_unreadable":
                hint = f"⚠️ 動態頁面：此網站需要 JavaScript 渲染。{hint}"
            
            return False, err, False, None, None, {
                "status": e.code,
                "hint": hint,
                "retryable": e.retryable,
                "http_status": e.http_status,
                "source": "scraper",
            }
        except Exception as e:
            sub.last_checked_at = now
            db.session.commit()
            err = str(e)
            if looks_like_anti_bot(err):
                record_blocked_site(app, sub.url, err)
            return False, err, False, None, None, {
                "status": "scrape_error",
                "hint": "抓取流程發生未分類錯誤，請稍後重試。",
                "retryable": True,
                "http_status": None,
                "source": "scraper",
            }

        last = sub.snapshots[0] if sub.snapshots else None
        sub.last_checked_at = now

        changed = bool(last and last.content_hash != new_hash)
        mail_sent: bool | None = None
        mail_error: str | None = None
        meaningful_change = False

        if changed:
            # 檢查變化是否具有意義
            meaningful_change = _is_meaningful_change(last.content_text or "", content_text)
            
        if changed and meaningful_change:
            sub.last_changed_at = now
            diff_summary = diff_to_summary(last.content_text or "", content_text)
            if _is_stdtime_subscription(sub):
                readable_summary = stdtime_diff_summary(last.content_text or "", content_text)
                if readable_summary:
                    diff_summary = readable_summary
            # 行政院公報：使用 Agent 2 產生視覺化差異報告
            if is_gazette_url(sub.url):
                gazette_report = generate_gazette_visual_report(
                    previous_snapshot=last.content_text or "",
                    current_snapshot=content_text,
                    api_key=app.config.get("GEMINI_API_KEY") or None,
                )
                if gazette_report:
                    diff_summary = gazette_report
            mail_sent, mail_error = send_change_email(app, sub, diff_summary)
            
            # 創建應用內通知
            notification = Notification(
                user_id=sub.user_id,
                subscription_id=sub.id,
                message=f"您的訂閱 '{sub.name or sub.url}' 有更新：{diff_summary[:1000]}"
            )
            db.session.add(notification)

        snapshot = Snapshot(
            subscription_id=sub.id,
            content_hash=new_hash,
            content_text=content_text[:50000],
            content_full=None,
        )
        db.session.add(snapshot)

        db.session.commit()
        return True, None, changed, mail_sent, mail_error, {
            "status": "ok",
            "hint": scrape_meta.get("hint") or "",
            "retryable": True,
            "http_status": None,
            "source": scrape_meta.get("source") or "unknown",
            "confidence": scrape_meta.get("confidence"),
        }


def _is_stdtime_subscription(sub: Subscription) -> bool:
    url = (sub.url or "").lower()
    return "stdtime.gov.tw" in url and "webclock" in url


def run_all_checks(app, stdtime_only: bool = False):
    """檢查所有訂閱（由排程或手動呼叫）。"""
    now = datetime.utcnow()
    with app.app_context():
        subs = Subscription.query.all()
        due_ids: list[int] = []
        for s in subs:
            if stdtime_only and not _is_stdtime_subscription(s):
                continue
            if not stdtime_only and _is_stdtime_subscription(s):
                continue

            if stdtime_only:
                interval_seconds = STDTIME_CHECK_INTERVAL_SECONDS
                if not s.last_checked_at:
                    due_ids.append(s.id)
                    continue
                delta = now - s.last_checked_at
                if delta.total_seconds() >= interval_seconds:
                    due_ids.append(s.id)
                continue

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

    def stdtime_job():
        run_all_checks(app, stdtime_only=True)

    def run_schedule():
        import schedule
        import time
        schedule.every(interval_minutes).minutes.do(job)
        schedule.every(STDTIME_CHECK_INTERVAL_SECONDS).seconds.do(stdtime_job)
        job()  # 啟動時先跑一次
        while True:
            schedule.run_pending()
            time.sleep(1)

    t = threading.Thread(target=run_schedule, daemon=True)
    t.start()
