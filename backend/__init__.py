import os
from flask import Flask
from flask_login import LoginManager
from sqlalchemy import inspect, text

from backend.config import Config
from backend.models import db, User

# 專案根目錄（NTU_AI）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_user_email_status_columns():
    inspector = inspect(db.engine)
    columns = {c["name"] for c in inspector.get_columns("users")}
    statements = []
    if "last_email_sent_at" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN last_email_sent_at DATETIME")
    if "last_email_success" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN last_email_success BOOLEAN")
    if "last_email_error" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN last_email_error TEXT")

    for stmt in statements:
        db.session.execute(text(stmt))
    if statements:
        db.session.commit()


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
        static_folder=os.path.join(BASE_DIR, "frontend", "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)
    db.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "請先登入。"

    @login_manager.unauthorized_handler
    def unauthorized_callback():
        from flask import request, jsonify, redirect, url_for

        # API 請求回傳 JSON，頁面請求才導向登入頁
        if request.path.startswith("/api/"):
            return jsonify({"error": "未授權，請先登入。"}), 401
        return redirect(url_for("auth.login"))

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        from backend.routes.auth import auth_bp
        from backend.routes.subscriptions import subscriptions_bp
        from backend.routes.pages import pages_bp
        from backend.routes.presets import presets_bp
        from backend.routes.blocked_sites import blocked_sites_bp
        app.register_blueprint(auth_bp, url_prefix="/auth")
        app.register_blueprint(subscriptions_bp, url_prefix="/api/subscriptions")
        app.register_blueprint(presets_bp, url_prefix="/api/presets")
        app.register_blueprint(blocked_sites_bp, url_prefix="/api/blocked-sites")
        app.register_blueprint(pages_bp)
        db.create_all()
        _ensure_user_email_status_columns()

    return app
