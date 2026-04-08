from flask import Blueprint, jsonify, current_app
from flask_login import login_required

from backend.services.blocked_sites import list_blocked_sites


blocked_sites_bp = Blueprint("blocked_sites", __name__)


@blocked_sites_bp.route("", methods=["GET"])
@login_required
def get_blocked_sites():
    return jsonify({"sites": list_blocked_sites(current_app)})

