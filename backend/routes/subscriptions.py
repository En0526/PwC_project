"""訂閱的 CRUD 與手動檢查、取得差異。"""
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from backend.models import db, Subscription, Snapshot
from backend.services.scraper import scrape_and_extract
from backend.services.diff_service import diff_to_summary
from backend.scheduler import run_check_subscription

subscriptions_bp = Blueprint("subscriptions", __name__)


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
                "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
                "last_changed_at": s.last_changed_at.isoformat() if s.last_changed_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
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
    sub = Subscription(
        user_id=current_user.id,
        url=url,
        name=name,
        watch_description=watch_description,
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({"id": sub.id, "url": sub.url, "name": sub.name, "watch_description": sub.watch_description}), 201


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
        "last_checked_at": sub.last_checked_at.isoformat() if sub.last_checked_at else None,
        "last_changed_at": sub.last_changed_at.isoformat() if sub.last_changed_at else None,
        "snapshots": [
            {"id": s.id, "captured_at": s.captured_at.isoformat() if s.captured_at else None}
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
    db.session.commit()
    return jsonify({"id": sub.id, "url": sub.url, "name": sub.name, "watch_description": sub.watch_description})


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
    run_check_subscription(sub_id, current_app)
    sub = Subscription.query.get(sub_id)
    return jsonify({
        "last_checked_at": sub.last_checked_at.isoformat() if sub.last_checked_at else None,
        "last_changed_at": sub.last_changed_at.isoformat() if sub.last_changed_at else None,
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
        "old_at": snapshots[1].captured_at.isoformat() if snapshots[1].captured_at else None,
        "new_at": snapshots[0].captured_at.isoformat() if snapshots[0].captured_at else None,
    })
