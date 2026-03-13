"""頁面：登入後的首頁（儀表板）、新增/管理訂閱。"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("pages.dashboard"))
    return redirect(url_for("auth.login"))


@pages_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")
