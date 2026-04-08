import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or "dev-secret-change-in-production"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///site.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or ""
    CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES") or "30")

    # Email notifications (optional)
    SMTP_HOST = os.environ.get("SMTP_HOST") or ""
    SMTP_PORT = int(os.environ.get("SMTP_PORT") or "587")
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME") or ""
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") or ""
    SMTP_FROM = os.environ.get("SMTP_FROM") or ""
    SMTP_USE_TLS = (os.environ.get("SMTP_USE_TLS") or "1").strip() not in ("0", "false", "False", "no", "NO")

    # 逗號分隔網域白名單。僅這些網域在憑證錯誤時可 fallback verify=False
    INSECURE_SSL_DOMAINS = os.environ.get("INSECURE_SSL_DOMAINS") or ""
