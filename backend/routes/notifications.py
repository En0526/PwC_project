from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from backend.models import db, Notification, Subscription

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

@notifications_bp.route("", methods=["GET"])
@login_required
def get_notifications():
    """取得使用者的所有通知"""
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    query = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    )

    total = query.count()
    notifications = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "notifications": [
            {
                "id": n.id,
                "subscription_id": n.subscription_id,
                "subscription_name": n.subscription.name or n.subscription.url,
                "title": n.title,
                "diff_summary": n.diff_summary,
                "is_read": n.is_read,
                "email_sent": n.email_sent,
                "created_at": n.created_at.isoformat()
            }
            for n in notifications
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }
    })

@notifications_bp.route("/<int:notif_id>", methods=["DELETE"])
@login_required
def delete_notification(notif_id):
    """刪除單個通知"""
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if not notif:
        return jsonify({"error": "找不到此通知"}), 404
    
    db.session.delete(notif)
    db.session.commit()
    return jsonify({"ok": True}), 200


@notifications_bp.route("/<int:notif_id>/read", methods=["PUT"])
@login_required
def mark_as_read(notif_id):
    """標記通知為已讀"""
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if not notif:
        return jsonify({"error": "找不到此通知"}), 404
    notif.is_read = True
    db.session.commit()
    return jsonify({"ok": True})

@notifications_bp.route("/mark-all-read", methods=["PUT"])
@login_required
def mark_all_as_read():
    """標記所有通知為已讀"""
    try:
        # 更新該用戶所有未讀通知為已讀
        updated_count = Notification.query.filter_by(
            user_id=current_user.id, 
            is_read=False
        ).update({"is_read": True})
        db.session.commit()
        
        return jsonify({
            "ok": True,
            "updated": updated_count
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@notifications_bp.route("/unread/count", methods=["GET"])
@login_required
def get_unread_count():
    """取得未讀通知數量"""
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({"unread_count": count})

@notifications_bp.route("/clear-all", methods=["DELETE"])
@login_required
def clear_all_notifications():
    """清除用戶的所有通知"""
    try:
        # 刪除用戶的所有通知
        deleted_count = Notification.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        return jsonify({
            "success": True, 
            "deleted_count": deleted_count,
            "message": f"已清除 {deleted_count} 條通知"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500