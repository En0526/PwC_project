"""訂閱的 CRUD 與手動檢查、取得差異。"""
from datetime import timezone, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from backend.models import db, Subscription, Snapshot
from backend.services.scraper import scrape_and_extract
from backend.services.diff_service import diff_to_summary
from backend.scheduler import run_check_subscription

CHECK_INTERVAL_OPTIONS = {
    60: "每小時",
    1440: "每天",
    10080: "每週",
    43200: "每月",
    129600: "每季",
}

subscriptions_bp = Blueprint("subscriptions", __name__)
TW_TZ = timezone(timedelta(hours=8))


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
        1440: "每天",
        10080: "每週",
        43200: "每月",
        129600: "每季",
    }
    return mapping.get(m, f"{m} 分鐘")


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
                "check_interval_label": interval_label(s.check_interval_minutes),
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
    if check_interval_minutes not in CHECK_INTERVAL_OPTIONS:
        return jsonify({"error": "檢查頻率未在可選項目中"}), 400
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
        "check_interval_label": interval_label(sub.check_interval_minutes),
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
        "check_interval_label": interval_label(sub.check_interval_minutes),
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
        if interval not in CHECK_INTERVAL_OPTIONS:
            return jsonify({"error": "檢查頻率未在可選項目中"}), 400
        sub.check_interval_minutes = interval
    db.session.commit()
    return jsonify({
        "id": sub.id,
        "url": sub.url,
        "name": sub.name,
        "watch_description": sub.watch_description,
        "check_interval_minutes": sub.check_interval_minutes,
        "check_interval_label": interval_label(sub.check_interval_minutes),
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
    ok, err, changed_internal, mail_sent, mail_error = run_check_subscription(sub_id, current_app)
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
        "last_checked_at": to_taiwan_iso(sub.last_checked_at),
        "last_changed_at": to_taiwan_iso(sub.last_changed_at),
    })


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
    summary = diff_to_summary(old_t, new_t)
    return jsonify({
        "diff_summary": summary,
        "old_at": to_taiwan_iso(snapshots[1].captured_at),
        "new_at": to_taiwan_iso(snapshots[0].captured_at),
    })
