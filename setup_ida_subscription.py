#!/usr/bin/env python3
"""
IDA RSS 訂閱管理工具

此腳本可以:
1. 直接在資料庫中新增 IDA RSS 訂閱
2. 為測試用戶自動設定訂閱
3. 驗證訂閱是否運行正常
"""

import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import create_app
from backend.models import db, User, Subscription
from werkzeug.security import generate_password_hash

# IDA RSS Feed 資訊
IDA_RSS_CONFIG = {
    "url": "https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=1",
    "name": "經濟部產業發展署新聞",
    "check_interval_minutes": 360,  # 6 小時
    "watch_description": None,  # 使用完整 RSS 內容
}

def create_test_user(app, email="test@example.com", password="test123456"):
    """建立測試用戶"""
    with app.app_context():
        # 檢查用戶是否已存在
        user = User.query.filter_by(email=email).first()
        if user:
            print(f"✓ 用戶已存在: {email}")
            return user
        
        # 建立新用戶
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        print(f"✓ 新用戶已建立: {email}")
        return user

def add_ida_subscription(app, user):
    """為用戶新增 IDA RSS 訂閱"""
    with app.app_context():
        # 檢查訂閱是否已存在
        existing = Subscription.query.filter_by(
            user_id=user.id,
            url=IDA_RSS_CONFIG["url"]
        ).first()
        
        if existing:
            print(f"✓ 訂閱已存在 (ID: {existing.id})")
            return existing
        
        # 建立新訂閱
        subscription = Subscription(
            user_id=user.id,
            url=IDA_RSS_CONFIG["url"],
            name=IDA_RSS_CONFIG["name"],
            check_interval_minutes=IDA_RSS_CONFIG["check_interval_minutes"],
            watch_description=IDA_RSS_CONFIG["watch_description"],
        )
        db.session.add(subscription)
        db.session.commit()
        
        print(f"""
✓ IDA RSS 訂閱已新增:
  - ID: {subscription.id}
  - 名稱: {subscription.name}
  - URL: {subscription.url}
  - 檢查頻率: {subscription.check_interval_minutes} 分鐘
  - 使用者: {user.email}
        """)
        return subscription

def list_user_subscriptions(app, user):
    """列出用戶的所有訂閱"""
    with app.app_context():
        subs = Subscription.query.filter_by(user_id=user.id).all()
        if not subs:
            print(f"✗ 用戶 {user.email} 沒有訂閱")
            return
        
        print(f"\n✓ 用戶 {user.email} 的訂閱列表:")
        print("-" * 80)
        for i, sub in enumerate(subs, 1):
            print(f"{i}. {sub.name or '(無名稱)'}")
            print(f"   URL: {sub.url}")
            print(f"   檢查頻率: {sub.check_interval_minutes} 分鐘")
            print(f"   建立時間: {sub.created_at}")
            print(f"   最後檢查: {sub.last_checked_at or '尚未檢查'}")
            print()

def main():
    """主程式"""
    print("="*80)
    print("IDA RSS 訂閱管理工具")
    print("="*80)
    
    # 建立應用
    app = create_app()
    
    with app.app_context():
        # 初始化資料庫
        print("\n[1] 初始化資料庫...")
        db.create_all()
        print("✓ 資料庫已初始化")
    
    # 建立或取得測試用戶
    print("\n[2] 建立或取得測試用戶...")
    user = create_test_user(app, email="ida_tracker@example.com", password="ida_tracking_2026")
    
    # 新增 IDA RSS 訂閱
    print("\n[3] 新增 IDA RSS 訂閱...")
    subscription = add_ida_subscription(app, user)
    
    # 列出用戶的所有訂閱
    print("\n[4] 驗證訂閱...")
    list_user_subscriptions(app, user)
    
    print("-" * 80)
    print("""
✅ 設定完成！

下一步:
1. 啟動應用: python app.py
2. 登入帳號: ida_tracker@example.com / ida_tracking_2026
3. 平台將在後台每 6 小時檢查一次 IDA RSS
4. 有新聞時將自動接收通知

測試手動檢查:
  curl -X POST http://localhost:5000/api/subscriptions/{}/check \\
    -H "Authorization: Bearer YOUR_TOKEN"
    
查詢訂閱狀態:
  curl http://localhost:5000/api/subscriptions/{} \\
    -H "Authorization: Bearer YOUR_TOKEN"
""".format(subscription.id, subscription.id))

if __name__ == "__main__":
    main()
