import os
from flask import Flask
from flask_login import LoginManager

from backend.config import Config
from backend.models import db, User

# 專案根目錄（NTU_AI）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
        static_folder=os.path.join(BASE_DIR, "frontend", "static"),
        static_url_path="",
    )
    app.config.from_object(config_class)
    db.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "請先登入。"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        from backend.routes.auth import auth_bp
        from backend.routes.subscriptions import subscriptions_bp
        from backend.routes.pages import pages_bp
        app.register_blueprint(auth_bp, url_prefix="/auth")
        app.register_blueprint(subscriptions_bp, url_prefix="/api/subscriptions")
        app.register_blueprint(pages_bp)
        db.create_all()

    return app
