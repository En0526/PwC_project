"""標準時間 WebClock：把擷取內容整理成可讀通知／差異摘要。"""
from __future__ import annotations

import re


def is_stdtime_webclock_url(url: str) -> bool:
    u = (url or "").lower()
    return "stdtime.gov.tw" in u and "webclock" in u


def _server_time_raw_to_display(raw: str) -> str | None:
    """
    API 回傳例如 2026-04-03T14:20:11.9622285+08:00
    輸出與頁面一致的日期時間字串（不帶毫秒）。
    """
    raw = (raw or "").strip().strip('"')
    m = re.match(
        r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?",
        raw,
    )
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}:{m.group(6)}"


def parse_server_time_line(text: str) -> str | None:
    """從擷取文字中的 `ServerTime:` 解析出顯示用時間。"""
    m = re.search(r"ServerTime:\s*([^\s\n]+)", text or "")
    if not m:
        return None
    return _server_time_raw_to_display(m.group(1))


def format_stdtime_snapshot_from_api_body(api_body: str) -> str:
    """
    GetServerTime API 回傳純字串時間；組成與頁面一致的兩行文字供儲存／比對。
    """
    raw = (api_body or "").strip().strip('"')
    disp = _server_time_raw_to_display(raw)
    if disp:
        return f"UTC(TL) : {disp}\nServerTime: {raw}"
    return f"ServerTime: {raw}"


def _extract_ui_stdtime_fields(text: str) -> dict[str, str]:
    """若擷取到的是網頁可見文字（含 UTC(TL) 等）。"""
    src = text or ""
    patterns = {
        "utc": r"UTC\(TL\)\s*[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}:[0-9]{2})",
        "device": r"本機時間\s*[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}:[0-9]{2})",
        "offset": r"與國家標準時間差\s*[:：]\s*([0-9]+(?:\.[0-9]+)?\s*ms)",
        "status": r"本機與主機狀態\s*[:：]\s*([A-Za-z]+)",
    }
    result: dict[str, str] = {}
    for key, pattern in patterns.items():
        m = re.search(pattern, src)
        if m:
            result[key] = m.group(1).strip()
    return result


def stdtime_diff_summary(old_text: str, new_text: str) -> str | None:
    """
    優先使用 API `ServerTime:` 兩次擷取比對；
    否則再嘗試網頁文字中的 UTC(TL)／本機時間等欄位。
    """
    old_srv = parse_server_time_line(old_text)
    new_srv = parse_server_time_line(new_text)
    if new_srv:
        lines = ["【標準時間更新】"]
        if old_srv and old_srv != new_srv:
            lines.append(f"UTC(TL) : {old_srv} -> {new_srv}")
        else:
            lines.append(f"UTC(TL) : {new_srv}")
        return "\n".join(lines)

    old_v = _extract_ui_stdtime_fields(old_text)
    new_v = _extract_ui_stdtime_fields(new_text)
    if not new_v:
        return None

    lines = ["【標準時間更新】"]
    if new_v.get("utc"):
        if old_v.get("utc") and old_v["utc"] != new_v["utc"]:
            lines.append(f"UTC(TL) : {old_v['utc']} -> {new_v['utc']}")
        else:
            lines.append(f"UTC(TL) : {new_v['utc']}")
    if new_v.get("device"):
        if old_v.get("device") and old_v["device"] != new_v["device"]:
            lines.append(f"本機時間 : {old_v['device']} -> {new_v['device']}")
        else:
            lines.append(f"本機時間 : {new_v['device']}")
    if new_v.get("offset"):
        lines.append(f"與國家標準時間差 : {new_v['offset']}")
    if new_v.get("status"):
        lines.append(f"本機與主機狀態 : {new_v['status']}")
    return "\n".join(lines)
