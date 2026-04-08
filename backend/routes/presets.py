from flask import Blueprint, jsonify, current_app
from flask_login import login_required
from urllib.parse import urlparse

from backend.services.blocked_sites import list_blocked_sites, looks_like_anti_bot
from backend.services.presets import get_presets


presets_bp = Blueprint("presets", __name__)


@presets_bp.route("", methods=["GET"])
@login_required
def list_presets():
    presets = get_presets()
    blocked_sites = list_blocked_sites(current_app)

    # 明確反爬站台，從常用清單中自動隱藏（首次命中就生效）
    blocked_hosts = set()
    for site in blocked_sites:
        err = site.get("last_error") or ""
        cnt = int(site.get("count") or 0)
        if cnt < 1 or not looks_like_anti_bot(err):
            continue
        try:
            host = (urlparse(site.get("url") or "").hostname or "").lower()
        except Exception:
            host = ""
        if host:
            blocked_hosts.add(host)

    filtered = []
    for p in presets:
        try:
            host = (urlparse(p.url).hostname or "").lower()
        except Exception:
            host = ""
        if host and host in blocked_hosts:
            continue
        filtered.append(p)

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
                for p in filtered
            ]
        }
    )

