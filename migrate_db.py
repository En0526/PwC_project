"""
資料庫遷移腳本 - 添加通知功能
運行此腳本來更新現有資料庫結構
"""
import sqlite3
import os

def migrate_database():
    """添加通知相關的資料庫表和欄位"""

    db_path = os.path.join(os.path.dirname(__file__), "instance", "site.db")

    if not os.path.exists(db_path):
        print("資料庫文件不存在，跳過遷移")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 檢查是否已有 notifications 表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
        if cursor.fetchone():
            print("notifications 表已存在，跳過創建")
        else:
            # 創建 notifications 表
            cursor.execute('''
                CREATE TABLE notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    subscription_id INTEGER NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    content TEXT,
                    diff_summary TEXT,
                    is_read BOOLEAN DEFAULT 0,
                    email_sent BOOLEAN DEFAULT 0,
                    email_sent_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
                )
            ''')
            print("✅ 創建 notifications 表")

        # 檢查 users 表是否已有 notify_email 欄位
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'notify_email' not in columns:
            # 添加 notify_email 欄位到 users 表
            cursor.execute("ALTER TABLE users ADD COLUMN notify_email BOOLEAN DEFAULT 1")
            print("✅ 添加 notify_email 欄位到 users 表")
        else:
            print("notify_email 欄位已存在")

        conn.commit()
        print("🎉 資料庫遷移完成！")

    except Exception as e:
        print(f"❌ 遷移失敗: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()