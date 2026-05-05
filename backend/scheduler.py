"""定時檢查所有訂閱的網站是否有更新，有則記錄並可通知。"""
from datetime import datetime
import threading

from backend.models import db, Subscription, Snapshot, Notification
from backend.services.scraper import scrape_and_extract, ScrapeFailure
from backend.services.diff_service import diff_to_summary
from backend.services.stdtime_notify import stdtime_diff_summary
from backend.services.email_service import send_change_email
from backend.services.blocked_sites import looks_like_anti_bot, record_blocked_site
from backend.services.change_agent import generate_change_report
from backend.services.notification_report import build_notifications_pdf
from backend.services.screenshot_service import capture_page_screenshot

STDTIME_CHECK_INTERVAL_SECONDS = 30
CHECK_RUN_LOCK = threading.Lock()
_SUBSCRIPTION_CHECK_LOCKS: dict[int, threading.Lock] = {}
_SUBSCRIPTION_LOCKS_GUARD = threading.Lock()


def _subscription_check_lock(sub_id: int) -> threading.Lock:
    """同一訂閱序號同時間只允許一個 run_check_subscription（避免排程與手動檢查並行→重複通知）。"""
    with _SUBSCRIPTION_LOCKS_GUARD:
        if sub_id not in _SUBSCRIPTION_CHECK_LOCKS:
            _SUBSCRIPTION_CHECK_LOCKS[sub_id] = threading.Lock()
        return _SUBSCRIPTION_CHECK_LOCKS[sub_id]


def _is_mof_family_subscription(sub: Subscription) -> bool:
    url = (sub.url or "").lower()
    return "mof.gov.tw" in url or "ntbna.gov.tw" in url


def _latest_snapshot_for_subscription(subscription_id: int) -> Snapshot | None:
    """以 captured_at + id 排序，確保「最新」在並行寫入時仍穩定。"""
    return (
        Snapshot.query
        .filter_by(subscription_id=subscription_id)
        .order_by(Snapshot.captured_at.desc(), Snapshot.id.desc())
        .first()
    )


def _latest_snapshot_has_screenshot(sub_id: int) -> bool:
    latest = _latest_snapshot_for_subscription(sub_id)
    if not latest:
        return False
    return "|screenshot:" in (latest.content_full or "")


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
    with _subscription_check_lock(sub_id):
        return _run_check_subscription_impl(sub_id, app)


def _run_check_subscription_impl(sub_id: int, app) -> tuple[bool, str | None, bool, bool | None, str | None, dict]:
    with app.app_context():
        sub = Subscription.query.get(sub_id)
        if not sub:
            return False, "找不到訂閱", False, None, None, {"status": "not_found"}
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

        sub.last_checked_at = now
        latest = _latest_snapshot_for_subscription(sub.id)

        # 本次擷取與資料庫最新版相同：不重複發通知／不重複寫快照（涵蓋短時間連續檢查）
        if latest and latest.content_hash and latest.content_hash == new_hash:
            db.session.commit()
            return True, None, False, None, None, {
                "status": "ok",
                "hint": scrape_meta.get("hint") or "",
                "retryable": True,
                "http_status": None,
                "source": scrape_meta.get("source") or "unknown",
                "confidence": scrape_meta.get("confidence"),
                "diff_summary": None,
                "dedupe": "content_hash_unchanged",
            }

        last = latest
        diff_summary: str | None = None
        changed = bool(last and last.content_hash != new_hash)
        mail_sent: bool | None = None
        mail_error: str | None = None
        meaningful_change = False
        suppressed_duplicate_race = False

        if changed:
            # 檢查變化是否具有意義
            meaningful_change = _is_meaningful_change(last.content_text or "", content_text)

        if changed and meaningful_change:
            race_latest = _latest_snapshot_for_subscription(sub.id)
            if race_latest and race_latest.content_hash and race_latest.content_hash == new_hash:
                meaningful_change = False
                suppressed_duplicate_race = True

        if changed and meaningful_change:
            sub.last_changed_at = now
            diff_summary = diff_to_summary(last.content_text or "", content_text)
            if _is_stdtime_subscription(sub):
                readable_summary = stdtime_diff_summary(last.content_text or "", content_text)
                if readable_summary:
                    diff_summary = readable_summary
            if not _is_stdtime_subscription(sub):
                diff_summary = generate_change_report(
                    url=sub.url,
                    site_name=sub.name or sub.url,
                    previous_snapshot=last.content_text or "",
                    current_snapshot=content_text,
                    watch_description=sub.watch_description,
                    fallback_summary=diff_summary,
                    api_key=app.config.get("GEMINI_API_KEY") or None,
                    model_name=app.config.get("AI_SUMMARY_MODEL") or None,
                )
            
            # 創建應用內通知
            notification = Notification(
                user_id=sub.user_id,
                subscription_id=sub.id,
                message=f"您的訂閱 '{sub.name or sub.url}' 有更新：{diff_summary[:1000]}"
            )
            db.session.add(notification)
            report_pdf_bytes: bytes | None = None
            if bool(app.config.get("AUTO_SEND_NOTIFICATION_REPORT", True)):
                limit = max(1, min(int(app.config.get("NOTIFICATION_REPORT_LIMIT", 20) or 20), 100))
                notifications = (
                    Notification.query
                    .filter_by(user_id=sub.user.id)
                    .order_by(Notification.created_at.desc())
                    .limit(limit)
                    .all()
                )
                report_pdf_bytes = build_notifications_pdf(
                    notifications,
                    user_email=sub.user.email,
                    max_rows=limit,
                )

            mail_sent, mail_error = send_change_email(
                app,
                sub,
                diff_summary,
                pdf_bytes=report_pdf_bytes,
            )
            sub.user.last_email_sent_at = now
            sub.user.last_email_success = bool(mail_sent)
            sub.user.last_email_error = mail_error

        screenshot_web_path = None
        should_capture = changed and meaningful_change
        # 財政部相關網站：即使本次未判定變更，也補一張基準截圖，避免 PDF 長期空白。
        if not should_capture and _is_mof_family_subscription(sub) and not _latest_snapshot_has_screenshot(sub.id):
            should_capture = True
        if should_capture:
            screenshot_web_path = capture_page_screenshot(sub.url)
        content_full_meta = f"source:{scrape_meta.get('source') or 'unknown'}"
        if screenshot_web_path:
            content_full_meta += f"|screenshot:{screenshot_web_path}"

        final_latest = _latest_snapshot_for_subscription(sub.id)
        if not (final_latest and final_latest.content_hash and final_latest.content_hash == new_hash):
            snapshot = Snapshot(
                subscription_id=sub.id,
                content_hash=new_hash,
                content_text=content_text[:50000],
                content_full=content_full_meta,
            )
            db.session.add(snapshot)

        db.session.commit()
        reported_changed = changed and not suppressed_duplicate_race
        return True, None, reported_changed, mail_sent, mail_error, {
            "status": "ok",
            "hint": scrape_meta.get("hint") or "",
            "retryable": True,
            "http_status": None,
            "source": scrape_meta.get("source") or "unknown",
            "confidence": scrape_meta.get("confidence"),
            "diff_summary": diff_summary if (changed and meaningful_change) else None,
        }


def _is_stdtime_subscription(sub: Subscription) -> bool:
    url = (sub.url or "").lower()
    return "stdtime.gov.tw" in url and "webclock" in url


def run_all_checks(app, stdtime_only: bool = False):
    """檢查所有訂閱（由排程或手動呼叫）。"""
    if not CHECK_RUN_LOCK.acquire(blocking=False):
        return
    try:
        _run_all_checks_internal(app, stdtime_only=stdtime_only)
    finally:
        CHECK_RUN_LOCK.release()


def _run_all_checks_internal(app, stdtime_only: bool = False):
    """Internal: run checks with caller-managed lock."""
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
            app.logger.exception("run_all_checks failed for subscription_id=%s", sub_id)


def init_scheduler(app):
    """
    啟動背景排程。

    注意：每則訂閱的「檢查間隔」由 Subscription.check_interval_minutes 決定；
    此處的輪詢間隔（SCHEDULER_POLL_MINUTES）是「多久喚醒一次去看誰到期」。
    若輪詢設成 30 分鐘、訂閱卻設每 1 分鐘，實際最多每 30 分鐘才會被評估一次。
    """
    poll_minutes = max(1, int(app.config.get("SCHEDULER_POLL_MINUTES", 1)))

    def job():
        run_all_checks(app)

    def stdtime_job():
        run_all_checks(app, stdtime_only=True)

    def run_schedule():
        import schedule
        import time
        schedule.every(poll_minutes).minutes.do(job)
        schedule.every(STDTIME_CHECK_INTERVAL_SECONDS).seconds.do(stdtime_job)
        job()  # 啟動時先跑一次
        while True:
            schedule.run_pending()
            time.sleep(1)

    t = threading.Thread(target=run_schedule, daemon=True)
    t.start()
