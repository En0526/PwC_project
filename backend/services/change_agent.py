"""Agent 2: compare old/new snapshots and produce notification-ready summaries."""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

from backend.services.diff_service import diff_to_summary
from backend.services.gazette_diff_agent import generate_gazette_visual_report
from backend.services.gazette_monitor_agent import is_gazette_url

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def generate_change_report(
    *,
    url: str,
    site_name: str,
    previous_snapshot: str,
    current_snapshot: str,
    fallback_summary: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
) -> str:
    """Generate a readable summary for a detected content change."""
    if is_gazette_url(url):
        gazette_report = generate_gazette_visual_report(
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            api_key=api_key,
            model_name=model_name,
        )
        if gazette_report:
            return gazette_report

    list_report = _section_list_report(
        site_name=site_name,
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        api_key=api_key,
        model_name=model_name,
    )
    if list_report:
        return list_report

    return fallback_summary or diff_to_summary(previous_snapshot, current_snapshot)


def _section_list_report(
    *,
    site_name: str,
    previous_snapshot: str,
    current_snapshot: str,
    api_key: str | None = None,
    model_name: str | None = None,
) -> str | None:
    prev_items = _extract_list_items(previous_snapshot)
    curr_items = _extract_list_items(current_snapshot)
    if not curr_items:
        return None

    prev_keys = {_item_key(item) for item in prev_items}
    curr_keys = {_item_key(item) for item in curr_items}
    added = [item for item in curr_items if _item_key(item) not in prev_keys]
    removed = [item for item in prev_items if _item_key(item) not in curr_keys]

    if not added and not removed and previous_snapshot:
        return None

    section_name = _extract_field(current_snapshot, "區塊") or "監測區塊"
    snapshot_site = _extract_field(current_snapshot, "站點") or site_name or "網站"
    total_records = _extract_field(current_snapshot, "總筆數")

    if api_key and genai:
        ai_report = _ai_section_list_report(
            site_name=snapshot_site,
            section_name=section_name,
            total_records=total_records,
            added=added,
            removed=removed,
            current_items=curr_items,
            api_key=api_key,
            model_name=model_name,
        )
        if ai_report:
            return ai_report

    return _basic_section_list_report(
        site_name=snapshot_site,
        section_name=section_name,
        total_records=total_records,
        added=added,
        removed=removed,
        current_items=curr_items,
        has_previous=bool(previous_snapshot),
    )


def _extract_list_items(snapshot: str | None) -> list[dict[str, str]]:
    if not snapshot:
        return []

    items = []
    in_list = False
    for line in snapshot.splitlines():
        stripped = line.strip()
        if stripped == "[新聞列表]":
            in_list = True
            continue
        if in_list and stripped.startswith("[") and not re.match(r"^\[\d{4}-\d{2}-\d{2}\]", stripped):
            break
        match = re.match(r"^\[(\d{4}-\d{2}-\d{2})\]\s+(.+?)(?:\s+\|\s+(.+))?$", stripped)
        if match:
            items.append({
                "date": match.group(1),
                "title": match.group(2).strip(),
                "url": (match.group(3) or "").strip(),
            })
            continue

        rss_match = re.match(r"^([^|]+)\s+\|\s+(.+?)\s+\|\s+([^|]+)\s+\|\s+(.+)$", stripped)
        if rss_match:
            items.append({
                "date": _normalize_item_date(rss_match.group(3).strip()),
                "title": rss_match.group(2).strip(),
                "url": rss_match.group(4).strip(),
                "id": rss_match.group(1).strip(),
            })
    return items


def _extract_field(snapshot: str | None, key: str) -> str:
    if not snapshot:
        return ""
    for line in snapshot.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"[{key}]"):
            return stripped.split("]", 1)[-1].strip()
    return ""


def _item_key(item: dict[str, str]) -> str:
    return item.get("url") or item.get("id") or f"{item.get('date', '')}|{item.get('title', '')}"


def _basic_section_list_report(
    *,
    site_name: str,
    section_name: str,
    total_records: str,
    added: list[dict[str, str]],
    removed: list[dict[str, str]],
    current_items: list[dict[str, str]],
    has_previous: bool,
) -> str:
    latest_date = _latest_item_date(current_items)
    recent_three_day_items = _items_since(current_items, latest_date, days=3)
    latest_day_added = _items_on_date(added, latest_date)
    older_added = [item for item in added if item not in latest_day_added]

    dash = "-" * 32
    lines = [f"{site_name}更新｜{section_name}"]
    if total_records:
        lines.append(f"目前總筆數：{total_records}")
    if latest_date:
        lines.append(f"近三日共更新：{len(recent_three_day_items)} 則新聞")
        lines.append(f"近一日新增：{len(latest_day_added)} 則")
    lines.append(dash)

    if latest_day_added:
        lines.append("近一日新增重點：")
        for i, item in enumerate(latest_day_added[:5], 1):
            lines.append(f"  {i}. [{item['date']}] {item['title']}")
            if item.get("url"):
                lines.append(f"     {item['url']}")
        if len(latest_day_added) > 5:
            lines.append(f"  另有 {len(latest_day_added) - 5} 則近一日新增新聞。")
    elif added:
        lines.append("新增內容：")
        for i, item in enumerate(added[:5], 1):
            lines.append(f"  {i}. [{item['date']}] {item['title']}")
            if item.get("url"):
                lines.append(f"     {item['url']}")
        if len(added) > 5:
            lines.append(f"  另有 {len(added) - 5} 則新增新聞。")
    elif not has_previous:
        lines.append("首次建立監測基準，目前最新內容：")
        for i, item in enumerate(current_items[:10], 1):
            lines.append(f"  {i}. [{item['date']}] {item['title']}")
    else:
        lines.append("列表內容有變化，但未偵測到新增項目。")

    if older_added:
        lines.append(dash)
        lines.append(f"其他新增：{len(older_added)} 則")
        for item in older_added[:5]:
            lines.append(f"  - [{item['date']}] {item['title']}")

    if removed:
        lines.append(dash)
        lines.append("移除內容：")
        for item in removed:
            lines.append(f"  - [{item['date']}] {item['title']}")

    return "\n".join(lines)


def _ai_section_list_report(
    *,
    site_name: str,
    section_name: str,
    total_records: str,
    added: list[dict[str, str]],
    removed: list[dict[str, str]],
    current_items: list[dict[str, str]],
    api_key: str,
    model_name: str | None = None,
) -> str | None:
    model_name = model_name or os.environ.get("AI_SUMMARY_MODEL") or "gemini-1.5-flash"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    added_block = "\n".join(_format_item(item) for item in added) or "（無新增）"
    removed_block = "\n".join(_format_item(item) for item in removed) or "（無移除）"
    latest_date = _latest_item_date(current_items)
    recent_three_count = len(_items_since(current_items, latest_date, days=3))
    latest_day_added = _items_on_date(added, latest_date)
    latest_day_added_block = "\n".join(_format_item(item) for item in latest_day_added) or "（無近一日新增）"

    prompt = f"""你是網站更新通知摘要 Agent。
請根據以下結構化列表差異，輸出繁體中文通知。只根據提供內容，不要臆測。

【站點】{site_name}
【區塊】{section_name}
【目前總筆數】{total_records or "未知"}
【最新日期】{latest_date.isoformat() if latest_date else "未知"}
【近三日新聞數】{recent_three_count}
【近一日新增數】{len(latest_day_added)}

【新增項目】
{added_block}

【近一日新增項目（請優先 highlight）】
{latest_day_added_block}

【移除項目】
{removed_block}

請輸出：
1. 第一行：{site_name}更新｜{section_name}
2. 第二、三行先寫「近三日共更新：N 則新聞」與「近一日新增：N 則」。
3. 接著以「近一日新增重點」列出最多 5 則近一日新增，保留日期與標題。
4. 若有其他日期新增或移除，再簡短列出數量與最多 3 則。
5. 最多 800 字，純文字，不使用 Markdown 標題。
"""
    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.1, "max_output_tokens": 700},
        )
        text = (getattr(response, "text", "") or "").strip()
        return text[:2500] if text else None
    except Exception:
        return None


def _format_item(item: dict[str, str]) -> str:
    url = item.get("url") or ""
    suffix = f" | {url}" if url else ""
    return f"[{item.get('date', '')}] {item.get('title', '')}{suffix}"


def _latest_item_date(items: list[dict[str, str]]) -> date | None:
    dates = [_parse_date(item.get("date", "")) for item in items]
    valid_dates = [item_date for item_date in dates if item_date is not None]
    return max(valid_dates) if valid_dates else None


def _items_since(items: list[dict[str, str]], latest_date: date | None, *, days: int) -> list[dict[str, str]]:
    if latest_date is None:
        return []
    start = latest_date - timedelta(days=max(days - 1, 0))
    return [
        item
        for item in items
        if (item_date := _parse_date(item.get("date", ""))) is not None
        and start <= item_date <= latest_date
    ]


def _items_on_date(items: list[dict[str, str]], target_date: date | None) -> list[dict[str, str]]:
    if target_date is None:
        return []
    return [
        item
        for item in items
        if _parse_date(item.get("date", "")) == target_date
    ]


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        pass
    try:
        return parsedate_to_datetime((value or "").replace("CST", "+0800")).date()
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def _normalize_item_date(value: str) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else value
