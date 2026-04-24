from flask import Blueprint, jsonify, current_app
from flask_login import login_required

from backend.services.presets import get_presets


presets_bp = Blueprint("presets", __name__)


@presets_bp.route("", methods=["GET"])
@login_required
def list_presets():
    presets = get_presets()

    return jsonify(
        {
            "presets": [
                {
                    "id": p.id,
                    "name": p.name,
                    "url": p.url,
                    "frequency": p.frequency,
                    "check_interval_minutes": p.check_interval_minutes,
                    "watch_description": p.watch_description,
                }
                for p in presets
            ]
        }
    )

