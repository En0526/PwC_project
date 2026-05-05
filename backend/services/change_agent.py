"""Agent 2: compare old/new snapshots and produce notification-ready summaries."""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

from backend.services.diff_service import diff_to_summary
from backend.services.gazette_diff_agent import generate_gazette_visual_report
from backend.services.gazette_monitor_agent import is_gazette_url
from backend.services.labuanfsa_monitor_agent import is_labuanfsa_url
from backend.services.labuanfsa_diff_agent import generate_labuanfsa_visual_report
from backend.services.ntbna_monitor_agent import is_ntbna_news_url
from backend.services.ntbna_diff_agent import generate_ntbna_diff_report
from backend.services.chinatimes_monitor_agent import is_chinatimes_home_url
from backend.services.chinatimes_diff_agent import generate_chinatimes_diff_report
from backend.services.mops_monitor_agent import is_mops_realtime_url
from backend.services.mops_diff_agent import generate_mops_diff_report
from backend.services.bingo_monitor_agent import is_bingo_bingo_url
from backend.services.bingo_diff_agent import generate_bingo_diff_report
from backend.services.oecd_beps_monitor_agent import is_oecd_beps_url
from backend.services.oecd_beps_diff_agent import generate_oecd_beps_diff_report
from backend.services.oecd_topics_diff_agent import (
    generate_oecd_topics_diff_report,
    is_oecd_topics_page_url,
)

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
    watch_description: str | None = None,
    fallback_summary: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
) -> str:
    """Generate a readable summary for a detected content change."""
    if is_mops_realtime_url(url):
        mops_report = generate_mops_diff_report(
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            api_key=api_key,
            model_name=model_name,
        )
        if mops_report:
            return mops_report

    if is_bingo_bingo_url(url):
        bingo_report = generate_bingo_diff_report(
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
        )
        if bingo_report:
            return bingo_report

    if is_oecd_beps_url(url):
        oecd_report = generate_oecd_beps_diff_report(
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            api_key=api_key,
            model_name=model_name,
        )
        if oecd_report:
            return oecd_report

    if is_oecd_topics_page_url(url):
        topics_report = generate_oecd_topics_diff_report(
            url=url,
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
        )
        if topics_report:
            return topics_report

    if is_ntbna_news_url(url):
        ntbna_report = generate_ntbna_diff_report(
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            api_key=api_key,
            model_name=model_name,
        )
        if ntbna_report:
            return ntbna_report

    if is_chinatimes_home_url(url):
        chinatimes_report = generate_chinatimes_diff_report(
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            api_key=api_key,
            model_name=model_name,
        )
        if chinatimes_report:
            return chinatimes_report

    if is_gazette_url(url):
        gazette_report = generate_gazette_visual_report(
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            api_key=api_key,
            model_name=model_name,
        )
        if gazette_report:
            return gazette_report

    if is_labuanfsa_url(url):
        labuan_report = generate_labuanfsa_visual_report(
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            api_key=api_key,
            model_name=model_name,
        )
        if labuan_report:
            return labuan_report

    list_report = _section_list_report(
        site_name=site_name,
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        watch_description=watch_description,
        api_key=api_key,
        model_name=model_name,
    )
    if list_report:
        return list_report

    if api_key and genai:
        ai_report = _ai_generic_change_report(
            url=url,
            site_name=site_name,
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            watch_description=watch_description,
            api_key=api_key,
            model_name=model_name,
        )
        if ai_report:
            return ai_report

    return fallback_summary or diff_to_summary(previous_snapshot, current_snapshot)


def _section_list_report(
    *,
    site_name: str,
    previous_snapshot: str,
    current_snapshot: str,
    watch_description: str | None = None,
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
    focus_keywords = _extract_focus_keywords(watch_description)
    focused_added = _filter_items_by_keywords(added, focus_keywords)
    focused_removed = _filter_items_by_keywords(removed, focus_keywords)
    focus_hint = _build_focus_hint(focus_keywords, focused_added, focused_removed)

    if api_key and genai:
        ai_report = _ai_section_list_report(
            site_name=snapshot_site,
            section_name=section_name,
            total_records=total_records,
            added=added,
            removed=removed,
            current_items=curr_items,
            watch_description=watch_description,
            focus_keywords=focus_keywords,
            focused_added=focused_added,
            focused_removed=focused_removed,
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
        focus_hint=focus_hint,
        focused_added=focused_added,
        focused_removed=focused_removed,
        has_previous=bool(previous_snapshot),
    )


def _ai_generic_change_report(
    *,
    url: str,
    site_name: str,
    previous_snapshot: str,
    current_snapshot: str,
    watch_description: str | None,
    api_key: str,
    model_name: str | None = None,
) -> str | None:
    """Use Gemini to create a human-readable generic page change summary."""
    model_name = model_name or os.environ.get("AI_SUMMARY_MODEL") or "gemini-1.5-flash"
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    before_text = _trim_for_ai(previous_snapshot, max_chars=3500)
    after_text = _trim_for_ai(current_snapshot, max_chars=3500)

    prompt = f"""你是網站差異說明助理，請用繁體中文幫一般使用者解釋網頁更新重點。
請只根據提供內容，不要臆測，避免空泛描述。

【站點】{site_name or "未命名網站"}
【URL】{url}
【使用者關注重點】{watch_description or "未指定"}

【更新前內容片段】
{before_text or "（無）"}

【更新後內容片段】
{after_text or "（無）"}

請輸出格式（純文字）：
1. 第一行：{site_name or "網站"}更新重點
2. 第二行：一句總結（例如：新增了哪些公告/異動了哪些條件）
3. 「主要變更」：列 2-5 點，聚焦使用者可能在意的具體改動
4. 「對使用者的影響」：1-2 句，說明可能要留意什麼

限制：
- 最多 350 字
- 不要貼整段原文
- 若變化僅為格式、時間戳或重複資訊，請明確說「主要為版面/時間更新，實質內容變化有限」
"""
    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.1, "max_output_tokens": 500},
        )
        text = (getattr(response, "text", "") or "").strip()
        return text[:1200] if text else None
    except Exception:
        return None


def _trim_for_ai(text: str | None, *, max_chars: int) -> str:
    if not text:
        return ""
    compact = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(compact) <= max_chars:
        return compact
    head = compact[: int(max_chars * 0.7)]
    tail = compact[-int(max_chars * 0.3):]
    return f"{head}\n\n...(中略)...\n\n{tail}"


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
    focus_hint: str,
    focused_added: list[dict[str, str]],
    focused_removed: list[dict[str, str]],
    has_previous: bool,
) -> str:
    latest_date = _latest_item_date(current_items)
    recent_three_day_items = _items_since(current_items, latest_date, days=3)
    latest_day_added = _items_on_date(added, latest_date)
    older_added = [item for item in added if item not in latest_day_added]

    dash = "-" * 32
    lines = [f"{site_name}更新｜{section_name}"]
    if latest_date:
        lines.append(f"近三日共更新：{len(recent_three_day_items)} 則新聞")
        lines.append(f"近一日新增：{len(latest_day_added)} 則")
    if focus_hint:
        lines.append(focus_hint)
    lines.append(dash)

    if latest_day_added:
        lines.append("近一日新增重點：")
        for i, item in enumerate(latest_day_added[:5], 1):
            lines.append(f"  {i}. [{item['date']}] {item['title']}")
        if len(latest_day_added) > 5:
            lines.append(f"  另有 {len(latest_day_added) - 5} 則近一日新增新聞。")
    elif added:
        lines.append("新增內容：")
        for i, item in enumerate(added[:5], 1):
            lines.append(f"  {i}. [{item['date']}] {item['title']}")
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

    if focused_added:
        lines.append(dash)
        lines.append("關注重點新增：")
        for i, item in enumerate(focused_added[:5], 1):
            lines.append(f"  {i}. [{item['date']}] {item['title']}")
        if len(focused_added) > 5:
            lines.append(f"  另有 {len(focused_added) - 5} 則符合關注條件的新增內容。")

    if removed:
        lines.append(dash)
        lines.append("移除內容：")
        for item in removed:
            lines.append(f"  - [{item['date']}] {item['title']}")

    if focused_removed:
        lines.append(dash)
        lines.append("關注重點移除：")
        for item in focused_removed[:5]:
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
    watch_description: str | None,
    focus_keywords: list[str],
    focused_added: list[dict[str, str]],
    focused_removed: list[dict[str, str]],
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
    focused_added_block = "\n".join(_format_item(item) for item in focused_added) or "（無符合關注條件的新增）"
    focused_removed_block = "\n".join(_format_item(item) for item in focused_removed) or "（無符合關注條件的移除）"

    prompt = f"""你是網站更新通知摘要 Agent。
請根據以下結構化列表差異，輸出繁體中文通知。只根據提供內容，不要臆測。

【站點】{site_name}
【區塊】{section_name}
【使用者想追蹤的重點】{watch_description or "未指定"}
【優先關鍵詞】{', '.join(focus_keywords) if focus_keywords else '未指定'}
【目前總筆數】{total_records or "未知"}
【最新日期】{latest_date.isoformat() if latest_date else "未知"}
【近三日新聞數】{recent_three_count}
【近一日新增數】{len(latest_day_added)}

【新增項目】
{added_block}

【近一日新增項目（請優先 highlight）】
{latest_day_added_block}

【符合使用者關注重點的新增項目】
{focused_added_block}

【移除項目】
{removed_block}

【符合使用者關注重點的移除項目】
{focused_removed_block}

請輸出：
1. 第一行：{site_name}更新｜{section_name}
2. 第二、三行只寫「近三日共更新：N 則新聞」與「近一日新增：N 則」，不要輸出目前總筆數。
3. 若有符合使用者關注重點的新增項目，優先以「關注重點新增」列出，聚焦法規、公告、澄清、公告送達或 watch_description 指向的資訊，不要被其他一般新聞分散。
4. 接著以「近一日新增重點」列出最多 5 則近一日新增，保留日期與標題。
5. 若有其他日期新增或移除，再簡短列出數量與最多 3 則。
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
    return f"[{item.get('date', '')}] {item.get('title', '')}"


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


def _extract_focus_keywords(watch_description: str | None) -> list[str]:
    if not watch_description:
        return []

    # 精確提取：用特定句型從 watch_description 找出枚舉關鍵詞
    # 例：「與法規、公告、政策發布、公告送達相關」「的澄清、說明、更正與公告送達資訊」
    focused_segments: list[str] = []
    precise_patterns = [
        # 「與 A、B、C 相關」句型
        r"與([\u4e00-\u9fff]{2,6}(?:[、，][\u4e00-\u9fff]{2,6}){1,10})相關",
        # 「的 A、B、C 與 D 資訊/項目」句型
        r"的([\u4e00-\u9fff]{2,6}(?:[、，][\u4e00-\u9fff]{2,6}){0,10}(?:與[\u4e00-\u9fff]{2,6})?)(?:資訊|項目)",
        # 「追蹤/包含 A、B、C」句型
        r"(?:追蹤|包含)([\u4e00-\u9fff]{2,6}(?:[、，][\u4e00-\u9fff]{2,6}){1,10})",
    ]
    for pattern in precise_patterns:
        for seg in re.findall(pattern, watch_description):
            focused_segments.extend(re.split(r"[、，與]", seg))

    if focused_segments:
        raw_tokens = [t.strip() for t in focused_segments if t.strip()]
    else:
        # Fallback：全文掃描
        normalized = re.sub(r"[，。；、,/()（）「」]", " ", watch_description)
        normalized = re.sub(r"(?:以及|與|及|和|或|跟)", " ", normalized)
        raw_tokens = re.findall(r"[\u4e00-\u9fff]{2,6}", normalized)

    stop_words = {
        "追蹤", "最新", "資訊", "內容", "網站", "部分", "更新", "關注", "以及", "相關", "如果", "是否",
        "這個", "頁面", "項目", "希望", "新增", "移除", "針對", "使用者", "自動", "網站的", "首頁",
        "監測", "列表", "觀察", "整理", "忽略", "不要", "提供", "包含", "一般", "宣傳性", "其他",
    }
    keywords: list[str] = []
    for token in raw_tokens:
        token = re.sub(r"(?:相關|資訊|項目|的)$", "", token)
        token = token.strip()
        if not token or token in stop_words or token.isdigit() or len(token) < 2:
            continue
        if token not in keywords:
            keywords.append(token)

    synonym_map = {
        "法規": ["法規", "法令", "命令", "草案", "修正", "規定", "辦法", "要點"],
        "公告": ["公告", "公告事項", "公告送達", "送達"],
        "公告送達": ["公告送達", "送達", "公告"],
        "政策": ["政策", "政策發布", "政策公告"],
        "政策發布": ["政策發布", "政策", "政策公告"],
        "澄清": ["澄清", "更正", "說明"],
        "本部新聞": ["本部新聞"],
        "即時新聞澄清": ["即時新聞澄清", "澄清"],
    }
    expanded: list[str] = []
    for keyword in keywords:
        for expanded_keyword in synonym_map.get(keyword, [keyword]):
            if expanded_keyword not in expanded:
                expanded.append(expanded_keyword)
    return expanded[:12]


def _filter_items_by_keywords(items: list[dict[str, str]], keywords: list[str]) -> list[dict[str, str]]:
    if not items or not keywords:
        return []

    matched: list[dict[str, str]] = []
    for item in items:
        haystack = " ".join(str(item.get(field, "")) for field in ("title", "date", "url")).lower()
        if any(keyword.lower() in haystack for keyword in keywords):
            matched.append(item)
    return matched


def _build_focus_hint(
    keywords: list[str],
    focused_added: list[dict[str, str]],
    focused_removed: list[dict[str, str]],
) -> str:
    if not keywords:
        return ""
    if focused_added or focused_removed:
        return f"關注條件命中：{', '.join(keywords[:5])}"
    return f"關注條件：{', '.join(keywords[:5])}（本次未命中新增或移除項目）"
