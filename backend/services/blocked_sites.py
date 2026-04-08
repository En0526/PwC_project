from __future__ import annotations

import json
import os
from datetime import datetime


def _blocked_file_path(app) -> str:
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "instance")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "blocked_sites.json")


def _load(app) -> dict:
    path = _blocked_file_path(app)
    if not os.path.exists(path):
        return {"sites": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sites": {}}


def _save(app, data: dict) -> None:
    path = _blocked_file_path(app)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def looks_like_anti_bot(error_message: str) -> bool:
    s = (error_message or "").lower()
    keywords = [
        "403",
        "forbidden",
        "cloudflare",
        "access denied",
        "bot",
        "captcha",
        "blocked",
    ]
    return any(k in s for k in keywords)


def record_blocked_site(app, url: str, error_message: str) -> None:
    data = _load(app)
    sites = data.setdefault("sites", {})
    entry = sites.get(url) or {
        "url": url,
        "count": 0,
        "first_seen_at": datetime.utcnow().isoformat(),
        "last_seen_at": None,
        "last_error": "",
    }
    entry["count"] = int(entry.get("count") or 0) + 1
    entry["last_seen_at"] = datetime.utcnow().isoformat()
    entry["last_error"] = (error_message or "")[:500]
    sites[url] = entry
    _save(app, data)


def list_blocked_sites(app) -> list[dict]:
    data = _load(app)
    sites = list((data.get("sites") or {}).values())
    sites.sort(key=lambda x: x.get("last_seen_at") or "", reverse=True)
    return sites

