"""
測試通知功能
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import create_app
from backend.models import db, User, Subscription, Notification
from backend.services.email_service import send_notification_email, record_notification

def test_notification():
    """測試通知功能"""
    app = create_app()

    with app.app_context():
        # 創建測試用戶
        test_user = User(
            email="test@example.com",
            password_hash="test",
            notify_email=True
        )
        db.session.add(test_user)
        db.session.commit()

        # 創建測試訂閱
        test_sub = Subscription(
            user_id=test_user.id,
            url="https://example.com",
            name="測試網站",
            watch_description="測試內容"
        )
        db.session.add(test_sub)
        db.session.commit()

        # 測試記錄通知
        diff_summary = "測試變更內容：\n+ 新增了測試文字\n- 刪除了舊文字"
        notif = record_notification(test_user.id, test_sub.id, diff_summary, False)

        print(f"✅ 通知記錄成功: ID={notif.id}")
        print(f"   標題: {notif.title}")
        print(f"   差異摘要: {notif.diff_summary[:50]}...")

        # 測試發送email（不會真的發送，因為沒有配置）
        try:
            email_sent = send_notification_email(test_user, test_sub, diff_summary)
            print(f"   Email發送測試: {'成功' if email_sent else '失敗（預期，因為沒有配置SMTP）'}")
        except Exception as e:
            print(f"   Email發送測試: 失敗 - {e}")

        # 清理測試資料
        db.session.delete(notif)
        db.session.delete(test_sub)
        db.session.delete(test_user)
        db.session.commit()

        print("🎉 通知功能測試完成！")

if __name__ == "__main__":
    test_notification()