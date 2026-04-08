from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    subscriptions = db.relationship("Subscription", backref="user", lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", lazy=True, cascade="all, delete-orphan")


class Subscription(db.Model):
    __tablename__ = "subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    url = db.Column(db.String(2048), nullable=False)
    watch_description = db.Column(db.Text, nullable=True)  # 使用者描述「要觀看是否有更新的部分」
    name = db.Column(db.String(200), nullable=True)  # 自訂名稱，例如「台大公告」
    check_interval_minutes = db.Column(db.Integer, default=30)
    last_checked_at = db.Column(db.DateTime, nullable=True)
    last_changed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    snapshots = db.relationship("Snapshot", backref="subscription", lazy=True, cascade="all, delete-orphan", order_by="Snapshot.captured_at.desc()")


class Snapshot(db.Model):
    __tablename__ = "snapshots"
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscriptions.id"), nullable=False)
    content_hash = db.Column(db.String(64), nullable=True)  # 用於快速判斷是否變更
    content_text = db.Column(db.Text, nullable=True)  # 擷取出的文字（依 watch_description 或全文）
    content_full = db.Column(db.Text, nullable=True)  # 可選：完整 HTML 或 text
    captured_at = db.Column(db.DateTime, server_default=db.func.now())


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscriptions.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
