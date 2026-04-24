"""訂閱的 CRUD 與手動檢查、取得差異。"""
from datetime import timezone, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from backend.models import db, Subscription, Snapshot, Notification
from backend.services.scraper import scrape_and_extract
from backend.services.diff_service import diff_to_summary
from backend.services.stdtime_notify import is_stdtime_webclock_url, stdtime_diff_summary
from backend.scheduler import run_check_subscription

CHECK_INTERVAL_OPTIONS = {
    60: "每小時",
    1440: "每天",
    10080: "每週",
    43200: "每月",
    129600: "每季",
    525600: "每年",
}

subscriptions_bp = Blueprint("subscriptions", __name__)
TW_TZ = timezone(timedelta(hours=8))
NOTIFICATION_PREVIEW_LIMIT = 6


def to_taiwan_iso(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TW_TZ).isoformat()


def interval_label(minutes):
    m = int(minutes or 30)
    mapping = {
        1: "每分鐘",
        60: "每小時",
        360: "6小時",
        1440: "每天",
        10080: "每週",
        43200: "每月",
        129600: "每季",
        525600: "每年",
    }
    return mapping.get(m, f"{m} 分鐘")


def interval_label_for_subscription(url, minutes):
    if is_stdtime_webclock_url(url):
        return "每30秒"
    return interval_label(minutes)


def serialize_notification(n, diff_cache=None):
    message = n.message or ""
    diff_summary = None
    display_message = message

    # 通知建立時就把差異摘要寫進 message；這裡直接解析，避免用「最新快照」重算而造成舊通知內容被覆蓋。
    marker = "有更新："
    if marker in message:
        prefix, suffix = message.split(marker, 1)
        display_message = (prefix + "有更新").strip()
        parsed = suffix.strip()
        if parsed.endswith("..."):
            parsed = parsed[:-3].rstrip()
        diff_summary = parsed or None

    return {
        "id": n.id,
        "subscription_id": n.subscription_id,
        "message": display_message,
        "diff_summary": diff_summary,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@subscriptions_bp.route("", methods=["GET"])
@login_required
def list_subscriptions():
    subs = Subscription.query.filter_by(user_id=current_user.id).order_by(Subscription.created_at.desc()).all()
    return jsonify({
        "subscriptions": [
            {
                "id": s.id,
                "url": s.url,
                "name": s.name,
                "watch_description": s.watch_description,
                "check_interval_minutes": s.check_interval_minutes,
                "check_interval_label": interval_label_for_subscription(s.url, s.check_interval_minutes),
                "last_checked_at": to_taiwan_iso(s.last_checked_at),
                "last_changed_at": to_taiwan_iso(s.last_changed_at),
                "created_at": to_taiwan_iso(s.created_at),
            }
            for s in subs
        ]
    })


@subscriptions_bp.route("", methods=["POST"])
@login_required
def create_subscription():
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "請提供網址 url"}), 400
    name = (data.get("name") or "").strip() or None
    watch_description = (data.get("watch_description") or "").strip() or None
    check_interval_minutes = data.get("check_interval_minutes")
    try:
        check_interval_minutes = int(check_interval_minutes) if check_interval_minutes is not None else 1440
    except (TypeError, ValueError):
        return jsonify({"error": "檢查頻率無效"}), 400
    if check_interval_minutes <= 0:
        return jsonify({"error": "檢查頻率需大於 0 分鐘"}), 400
    force_create = bool(data.get("force_create"))
    norm_url = url.lower()
    norm_watch = (watch_description or "").strip().lower()
    if not force_create:
        existing = Subscription.query.filter_by(user_id=current_user.id).all()
        duplicate = next(
            (
                s
                for s in existing
                if (s.url or "").strip().lower() == norm_url
                and ((s.watch_description or "").strip().lower() == norm_watch)
            ),
            None,
        )
        if duplicate:
            return jsonify({
                "error": "你已加入相同網站與監看區塊，是否仍要重複加入？",
                "requires_confirmation": True,
                "duplicate_subscription_id": duplicate.id,
            }), 409
    sub = Subscription(
        user_id=current_user.id,
        url=url,
        name=name,
        watch_description=watch_description,
        check_interval_minutes=check_interval_minutes,
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({
        "id": sub.id,
        "url": sub.url,
        "name": sub.name,
        "watch_description": sub.watch_description,
        "check_interval_minutes": sub.check_interval_minutes,
        "check_interval_label": interval_label_for_subscription(sub.url, sub.check_interval_minutes),
    }), 201


@subscriptions_bp.route("/<int:sub_id>", methods=["GET"])
@login_required
def get_subscription(sub_id):
    sub = Subscription.query.filter_by(id=sub_id, user_id=current_user.id).first()
    if not sub:
        return jsonify({"error": "找不到此訂閱"}), 404
    snapshots = Snapshot.query.filter_by(subscription_id=sub.id).order_by(Snapshot.captured_at.desc()).limit(10).all()
    return jsonify({
        "id": sub.id,
        "url": sub.url,
        "name": sub.name,
        "watch_description": sub.watch_description,
        "check_interval_minutes": sub.check_interval_minutes,
        "check_interval_label": interval_label_for_subscription(sub.url, sub.check_interval_minutes),
        "last_checked_at": to_taiwan_iso(sub.last_checked_at),
        "last_changed_at": to_taiwan_iso(sub.last_changed_at),
        "snapshots": [
            {"id": s.id, "captured_at": to_taiwan_iso(s.captured_at)}
            for s in snapshots
        ],
    })


@subscriptions_bp.route("/<int:sub_id>", methods=["PUT"])
@login_required
def update_subscription(sub_id):
    sub = Subscription.query.filter_by(id=sub_id, user_id=current_user.id).first()
    if not sub:
        return jsonify({"error": "找不到此訂閱"}), 404
    data = request.get_json() or {}
    if "url" in data:
        sub.url = (data["url"] or "").strip() or sub.url
    if "name" in data:
        sub.name = (data["name"] or "").strip() or None
    if "watch_description" in data:
        sub.watch_description = (data["watch_description"] or "").strip() or None
    if "check_interval_minutes" in data:
        try:
            interval = int(data["check_interval_minutes"])
        except (TypeError, ValueError):
            return jsonify({"error": "檢查頻率無效"}), 400
        if interval <= 0:
            return jsonify({"error": "檢查頻率需大於 0 分鐘"}), 400
        sub.check_interval_minutes = interval
    db.session.commit()
    return jsonify({
        "id": sub.id,
        "url": sub.url,
        "name": sub.name,
        "watch_description": sub.watch_description,
        "check_interval_minutes": sub.check_interval_minutes,
        "check_interval_label": interval_label_for_subscription(sub.url, sub.check_interval_minutes),
    })


@subscriptions_bp.route("/<int:sub_id>", methods=["DELETE"])
@login_required
def delete_subscription(sub_id):
    sub = Subscription.query.filter_by(id=sub_id, user_id=current_user.id).first()
    if not sub:
        return jsonify({"error": "找不到此訂閱"}), 404
    db.session.delete(sub)
    db.session.commit()
    return jsonify({"ok": True}), 200


@subscriptions_bp.route("/<int:sub_id>/check", methods=["POST"])
@login_required
def check_now(sub_id):
    sub = Subscription.query.filter_by(id=sub_id, user_id=current_user.id).first()
    if not sub:
        return jsonify({"error": "找不到此訂閱"}), 404
    before_changed_at = sub.last_changed_at
    ok, err, changed_internal, mail_sent, mail_error, diagnostic = run_check_subscription(sub_id, current_app)
    sub = Subscription.query.get(sub_id)
    changed_this_check = False
    if ok and sub and sub.last_changed_at:
        if before_changed_at is None or sub.last_changed_at > before_changed_at:
            changed_this_check = True
    return jsonify({
        "ok": ok,
        "error": err,
        "changed": changed_this_check or changed_internal,
        "mail_sent": mail_sent,
        "mail_error": mail_error,
        "result_status": (diagnostic or {}).get("status"),
        "hint": (diagnostic or {}).get("hint"),
        "retryable": (diagnostic or {}).get("retryable"),
        "source": (diagnostic or {}).get("source"),
        "confidence": (diagnostic or {}).get("confidence"),
        "last_checked_at": to_taiwan_iso(sub.last_checked_at),
        "last_changed_at": to_taiwan_iso(sub.last_changed_at),
    })


@subscriptions_bp.route("/check-all", methods=["POST"])
@login_required
def check_all_now():
    subs = Subscription.query.filter_by(user_id=current_user.id).all()
    if not subs:
        return jsonify({"ok": True, "checked_count": 0, "changed_count": 0, "messages": ["目前沒有任何追蹤項目。"]})

    checked_count = 0
    changed_count = 0
    results = []

    for sub in subs:
        checked_count += 1
        try:
            ok, err, changed_internal, mail_sent, mail_error, diagnostic = run_check_subscription(sub.id, current_app)
            if changed_internal:
                changed_count += 1
            message = None
            if ok:
                if changed_internal:
                    message = f"手動檢查：您的訂閱 '{sub.name or sub.url}' 已檢查，並發現更新。"
                else:
                    message = f"手動檢查：您的訂閱 '{sub.name or sub.url}' 已檢查，暫時無變更。"
                notification = Notification(
                    user_id=current_user.id,
                    subscription_id=sub.id,
                    message=message,
                )
                db.session.add(notification)
            else:
                status = (diagnostic or {}).get("status") or "failed"
                hint = (diagnostic or {}).get("hint") or ""
                message = f"手動檢查失敗：'{sub.name or sub.url}'（{status}）。"
                if hint:
                    message += f" 建議：{hint}"
                notification = Notification(
                    user_id=current_user.id,
                    subscription_id=sub.id,
                    message=message,
                )
                db.session.add(notification)
            results.append({
                "subscription_id": sub.id,
                "ok": ok,
                "changed": changed_internal,
                "error": err,
                "result_status": (diagnostic or {}).get("status"),
                "hint": (diagnostic or {}).get("hint"),
                "retryable": (diagnostic or {}).get("retryable"),
                "source": (diagnostic or {}).get("source"),
            })
        except Exception as e:
            message = f"手動檢查錯誤：'{sub.name or sub.url}' 發生例外。"
            notification = Notification(
                user_id=current_user.id,
                subscription_id=sub.id,
                message=message,
            )
            db.session.add(notification)
            results.append({
                "subscription_id": sub.id,
                "ok": False,
                "changed": False,
                "error": str(e),
                "result_status": "exception",
                "hint": "後端處理時發生例外，請查看伺服器日誌。",
                "retryable": True,
                "source": "backend",
            })

    db.session.commit()
    return jsonify({
        "ok": True,
        "checked_count": checked_count,
        "changed_count": changed_count,
        "results": results,
    })


@subscriptions_bp.route("/all", methods=["DELETE"])
@login_required
def delete_all_subscriptions():
    subs = Subscription.query.filter_by(user_id=current_user.id).all()
    for sub in subs:
        db.session.delete(sub)
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"ok": True, "deleted_subscriptions": len(subs)})


@subscriptions_bp.route("/<int:sub_id>/diff")
@login_required
def get_diff(sub_id):
    """取得最近一次變更與前一次的差異摘要。"""
    sub = Subscription.query.filter_by(id=sub_id, user_id=current_user.id).first()
    if not sub:
        return jsonify({"error": "找不到此訂閱"}), 404
    snapshots = Snapshot.query.filter_by(subscription_id=sub.id).order_by(Snapshot.captured_at.desc()).limit(2).all()
    if len(snapshots) < 2:
        return jsonify({"diff_summary": "尚無兩次擷取可比較。", "old_at": None, "new_at": None})
    old_t, new_t = snapshots[1].content_text or "", snapshots[0].content_text or ""
    summary = None
    if is_stdtime_webclock_url(sub.url):
        summary = stdtime_diff_summary(old_t, new_t)
    if not summary:
        summary = diff_to_summary(old_t, new_t)
    return jsonify({
        "diff_summary": summary,
        "old_at": to_taiwan_iso(snapshots[1].captured_at),
        "new_at": to_taiwan_iso(snapshots[0].captured_at),
    })


@subscriptions_bp.route("/notifications", methods=["GET"])
@login_required
def list_notifications():
    # 最多返回 6 則最新通知
    notifications = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(NOTIFICATION_PREVIEW_LIMIT)
        .all()
    )
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({
        "notifications": [serialize_notification(n) for n in notifications],
        "has_more": Notification.query.filter_by(user_id=current_user.id).count() > NOTIFICATION_PREVIEW_LIMIT,
        "unread_count": unread_count,
    })


@subscriptions_bp.route("/notifications/all", methods=["GET"])
@login_required
def list_all_notifications():
    # 返回所有通知（用於展開功能）
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return jsonify({
        "notifications": [serialize_notification(n) for n in notifications]
    })


@subscriptions_bp.route("/notifications/<int:notif_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if not notif:
        return jsonify({"error": "找不到此通知"}), 404
    notif.is_read = True
    db.session.commit()
    return jsonify({"ok": True}), 200


@subscriptions_bp.route("/notifications/<int:notif_id>", methods=["DELETE"])
@login_required
def delete_notification(notif_id):
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if not notif:
        return jsonify({"error": "找不到此通知"}), 404
    db.session.delete(notif)
    db.session.commit()
    return jsonify({"ok": True}), 200


@subscriptions_bp.route("/notifications/all", methods=["DELETE"])
@login_required
def delete_all_notifications():
    deleted_count = Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"ok": True, "deleted_count": deleted_count}), 200


# ============ RSS 功能相關端點 ============


@subscriptions_bp.route("/rss/detect", methods=["POST"])
@login_required
def detect_rss_feeds():
    """從指定 URL 的頁面偵測 RSS feed 鏈接。"""
    from backend.services.scraper import detect_rss_feeds, fetch_page_detailed
    
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    
    if not url:
        return jsonify({"error": "請提供網址"}), 400
    
    try:
        html, _ = fetch_page_detailed(url, timeout=10)
        feeds = detect_rss_feeds(html, base_url=url)
        
        return jsonify({
            "url": url,
            "feeds": feeds,
            "found": len(feeds) > 0,
            "message": f"找到 {len(feeds)} 個 RSS feed" if feeds else "此頁面未發現 RSS feed"
        }), 200
    
    except Exception as e:
        return jsonify({
            "url": url,
            "feeds": [],
            "found": False,
            "message": f"無法檢測 RSS：{str(e)}"
        }), 400


@subscriptions_bp.route("/rss/validate", methods=["POST"])
@login_required
def validate_rss_feed():
    """驗證指定的 URL 是否提供有效的 RSS feed。"""
    from backend.services.scraper import validate_rss_feed as validate_feed
    
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    
    if not url:
        return jsonify({"error": "請提供 RSS 網址"}), 400
    
    result = validate_feed(url, timeout=10)
    
    return jsonify({
        "url": url,
        **result
    }), (200 if result["valid"] else 400)

