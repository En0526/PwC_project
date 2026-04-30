"""Agent 2: compare old/new snapshots and produce notification-ready summaries."""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

from backend.services.diff_service import diff_to_summary
from backend.services.gazette_diff_agent import generate_gazette_visual_report
from backend.services.gazette_monitor_agent import is_gazette_url
from backend.services.ntbna_monitor_agent import is_ntbna_news_url
from backend.services.ntbna_diff_agent import generate_ntbna_diff_report
from backend.services.chinatimes_monitor_agent import is_chinatimes_home_url
from backend.services.chinatimes_diff_agent import generate_chinatimes_diff_report
from backend.services.mops_monitor_agent import is_mops_realtime_url
from backend.services.mops_diff_agent import generate_mops_diff_report

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

    list_report = _section_list_report(
        site_name=site_name,
        source_url=url,
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        watch_description=watch_description,
        api_key=api_key,
        model_name=model_name,
    )
    if list_report:
        return list_report

    return fallback_summary or diff_to_summary(previous_snapshot, current_snapshot)


def _source_url_is_structured_rss_feed(url: str) -> bool:
    """與 parse_rss_snapshot 產出之 [新聞列表] 對應的訂閱 URL；固定走 basic 摘要避免 LLM 改寫用語。"""
    u = (url or "").lower()
    return any(
        pat in u
        for pat in (
            "/rss/",
            "newsrssdetail",
            "rssview",
            "pro=rss.",
        )
    )


def _section_list_report(
    *,
    site_name: str,
    source_url: str = "",
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

    structured = _has_structured_news_list(current_snapshot)
    # RSS／列表快照常因 [站點]、[區塊]、[筆數] 或排序微調而 hash 變更，但項目 URL 集合相同；
    # 若此時 return None 會落到 diff_to_summary，對結構化文字做字元 diff 產生垃圾摘要。
    if not added and not removed and previous_snapshot and not structured:
        return None

    section_name = _extract_field(current_snapshot, "區塊") or "監測區塊"
    snapshot_site = _extract_field(current_snapshot, "站點") or site_name or "網站"
    total_records = _extract_field(current_snapshot, "總筆數") or _extract_field(current_snapshot, "筆數")
    focus_keywords = _extract_focus_keywords(watch_description)
    focused_added = _filter_items_by_keywords(added, focus_keywords)
    focused_removed = _filter_items_by_keywords(removed, focus_keywords)

    # 僅表頭／格式變更時不呼叫 LLM，避免「無新增」卻產生不穩定摘要
    force_basic_only = structured and previous_snapshot and not added and not removed
    skip_ai_rss = structured and _source_url_is_structured_rss_feed(source_url)

    if api_key and genai and not force_basic_only and not skip_ai_rss:
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
        focused_added=focused_added,
        focused_removed=focused_removed,
        has_previous=bool(previous_snapshot),
        structured_list=structured,
        source_url=source_url,
    )


def _normalize_snapshot_text(snapshot: str | None) -> str:
    if not snapshot:
        return ""
    return (snapshot.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _extract_list_items(snapshot: str | None) -> list[dict[str, str]]:
    if not snapshot:
        return []

    snapshot = _normalize_snapshot_text(snapshot)
    items: list[dict[str, str]] = []
    in_list = False
    # 選擇性子欄標籤：經濟部產業發展署 t=1 稿件分類〔新聞發布／產業大小事〕
    _lane_rx = r"(?:\[(新聞發布|產業大小事)\]\s+)?"
    for line in snapshot.splitlines():
        stripped = line.strip()
        if stripped == "[新聞列表]":
            in_list = True
            continue
        if in_list and stripped.startswith("[") and not re.match(r"^\[\d{4}-\d{2}-\d{2}\]", stripped):
            break
        match = re.match(
            rf"^\[(\d{{4}}-\d{{2}}-\d{{2}})\]\s*{_lane_rx}(.+?)(?:\s+\|\s+(.+))?$",
            stripped,
        )
        if match:
            lane_part = match.group(2)
            tit = match.group(3).strip()
            url_part = (match.group(4) or "").strip()
            items.append({
                "date": match.group(1),
                "lane": lane_part or "",
                "title": _clean_item_title(tit),
                "url": url_part,
            })
            continue

        rss_match = re.match(r"^([^|]+)\s+\|\s+(.+?)\s+\|\s+([^|]+)\s+\|\s+(.+)$", stripped)
        if rss_match:
            items.append({
                "date": _normalize_item_date(rss_match.group(3).strip()),
                "title": _clean_item_title(rss_match.group(2).strip()),
                "url": rss_match.group(4).strip(),
                "id": rss_match.group(1).strip(),
                "lane": "",
            })
    return items


def _has_structured_news_list(snapshot: str | None) -> bool:
    """與 parse_rss_snapshot / 列表監測共用之結構化區塊標記。"""
    return bool(snapshot and "[新聞列表]" in _normalize_snapshot_text(snapshot))


def _extract_field(snapshot: str | None, key: str) -> str:
    if not snapshot:
        return ""
    snapshot = _normalize_snapshot_text(snapshot)
    for line in snapshot.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"[{key}]"):
            return stripped.split("]", 1)[-1].strip()
    return ""


def _clean_item_title(title: str) -> str:
    title = re.sub(r"（\s*\d+(?:\.\d+)+(?:\s+\d{1,2}:\d{2})?\s*）", "", title)
    title = re.sub(r"\(\s*\d+(?:\.\d+)+(?:\s+\d{1,2}:\d{2})?\s*\)", "", title)
    title = title.replace("▍", "").strip()
    return title


def _item_key(item: dict[str, str]) -> str:
    return item.get("url") or item.get("id") or f"{item.get('date', '')}|{item.get('title', '')}"


def _is_ida_t1_rssview_url(url: str) -> bool:
    """產發署最新消息聯播（t=1），稿件可能分列「新聞發布」「產業大小事」。"""
    low = (url or "").lower()
    if "ida.gov.tw" not in low or "rssview" not in low:
        return False
    m = re.search(r"[\?&]t=(\d+)", url or "", flags=re.I)
    return bool(m) and int(m.group(1)) == 1


def _items_carry_sidebar_lane(items: list[dict[str, str]]) -> bool:
    return any((it.get("lane") or "").strip() for it in items)


def _compose_basic_news_block(
    *,
    site_name: str,
    section_display: str,
    current_items: list[dict[str, str]],
    added: list[dict[str, str]],
    focused_added: list[dict[str, str]],
    has_previous: bool,
    structured_list: bool,
) -> str:
    latest_date = _latest_item_date(current_items)
    recent_three_day_items = _items_since(current_items, latest_date, days=3)
    latest_day_items = _items_on_date(current_items, latest_date)
    latest_day_added = _items_on_date(added, latest_date)

    dash = "-" * 32
    lines = [f"{site_name}更新｜{section_display}"]
    if latest_date:
        lines.append(f"近三日共更新：{len(recent_three_day_items)} 則新聞")
        lines.append(f"今日新增：{len(latest_day_items)}則")

    if latest_day_items:
        lines.append("最近新增：")
        for i, item in enumerate(latest_day_items[:5], 1):
            lines.append(f"  {i}.  [{item['date']}] {item['title']}")
        if len(latest_day_items) > 5:
            lines.append(f"  另有 {len(latest_day_items) - 5} 則最近新增新聞。")
    elif added:
        lines.append("最近新增：")
        for i, item in enumerate(added[:5], 1):
            lines.append(f"  {i}.  [{item['date']}] {item['title']}")
        if len(added) > 5:
            lines.append(f"  另有 {len(added) - 5} 則新增新聞。")
    elif not has_previous:
        lines.append("首次建立監測基準，目前最新內容：")
        for i, item in enumerate(current_items[:10], 1):
            lines.append(f"  {i}. [{item['date']}] {item['title']}")
    elif structured_list:
        lines.append(
            f"（{section_display}）偵測到列表呈現或表頭資訊有更新，但與上次比對之新聞項目相同（無新增／移除項目）。"
        )
    else:
        lines.append("列表內容有變化，但未偵測到新增項目。")

    if focused_added:
        lines.append(dash)
        lines.append("關注重點新增：")
        for i, item in enumerate(focused_added[:5], 1):
            lines.append(f"  {i}. [{item['date']}] {item['title']}")
        if len(focused_added) > 5:
            lines.append(f"  另有 {len(focused_added) - 5} 則符合關注條件的新增內容。")

    return "\n".join(lines)


def _basic_section_list_report(
    *,
    site_name: str,
    section_name: str,
    total_records: str,
    added: list[dict[str, str]],
    removed: list[dict[str, str]],
    current_items: list[dict[str, str]],
    focused_added: list[dict[str, str]],
    focused_removed: list[dict[str, str]],
    has_previous: bool,
    structured_list: bool = False,
    source_url: str = "",
) -> str:
    if (
        structured_list
        and _is_ida_t1_rssview_url(source_url)
        and _items_carry_sidebar_lane(current_items)
    ):
        blocks: list[str] = []
        for lane_key in ("新聞發布", "產業大小事"):
            lane_cur = [it for it in current_items if it.get("lane") == lane_key]
            if not lane_cur:
                continue
            lane_added = [it for it in added if it.get("lane") == lane_key]
            lane_focus = [it for it in focused_added if it.get("lane") == lane_key]
            blocks.append(
                _compose_basic_news_block(
                    site_name=site_name,
                    section_display=lane_key,
                    current_items=lane_cur,
                    added=lane_added,
                    focused_added=lane_focus,
                    has_previous=has_previous,
                    structured_list=structured_list,
                )
            )
        if blocks:
            return "\n\n".join(blocks)

    return _compose_basic_news_block(
        site_name=site_name,
        section_display=section_name,
        current_items=current_items,
        added=added,
        focused_added=focused_added,
        has_previous=has_previous,
        structured_list=structured_list,
    )


def digest_news_list_snapshot(snapshot_text: str, site_name_fallback: str) -> str | None:
    """
    從「單一筆」結構化快照產生前幾則列表摘要（不做新舊比對）。
    供舊通知仍存字字 diff 垃圾時，改用最新快照顯示可讀內容。
    """
    snap = _normalize_snapshot_text(snapshot_text)
    items = _extract_list_items(snap)
    if not items:
        return None

    site = _extract_field(snap, "站點") or site_name_fallback or "網站"
    section = _extract_field(snap, "區塊") or "監測區塊"

    lanes_present = {(it.get("lane") or "").strip() for it in items if (it.get("lane") or "").strip()}
    if lanes_present and lanes_present <= {"新聞發布", "產業大小事"}:
        parts: list[str] = []
        for lk in ("新聞發布", "產業大小事"):
            sub = [it for it in items if it.get("lane") == lk]
            if not sub:
                continue
            latest_date = _latest_item_date(sub)
            recent_three = _items_since(sub, latest_date, days=3)
            latest_day = _items_on_date(sub, latest_date)
            buf = [f"{site}更新｜{lk}"]
            if latest_date:
                buf.append(f"近三日共更新：{len(recent_three)} 則新聞")
                buf.append(f"今日新增：{len(latest_day)}則")
            preview = latest_day if latest_day else sorted(
                sub,
                key=lambda it: (_parse_date(it.get("date", "")) or date.min),
                reverse=True,
            )
            buf.append("快照列表概要（最近一次擷取，供檢視舊通知之用）：")
            for i, it in enumerate(preview[:10], 1):
                buf.append(f"  {i}.  [{it.get('date', '')}] {it.get('title', '')}")
            parts.append("\n".join(buf))
        if parts:
            return "\n\n".join(parts)

    latest_date = _latest_item_date(items)
    recent_three = _items_since(items, latest_date, days=3)
    latest_day = _items_on_date(items, latest_date)

    lines = [f"{site}更新｜{section}"]
    if latest_date:
        lines.append(f"近三日共更新：{len(recent_three)} 則新聞")
        lines.append(f"今日新增：{len(latest_day)}則")

    preview = latest_day if latest_day else sorted(
        items,
        key=lambda it: (_parse_date(it.get("date", "")) or date.min),
        reverse=True,
    )
    lines.append("快照列表概要（最近一次擷取，供檢視舊通知之用）：")
    for i, item in enumerate(preview[:10], 1):
        lines.append(f"  {i}.  [{item.get('date', '')}] {item.get('title', '')}")

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
    try:
        model_name = model_name or os.environ.get("AI_SUMMARY_MODEL") or "gemini-1.5-flash"
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        added_block = "\n".join(_format_item(item) for item in added) or "（無新增）"
        latest_date = _latest_item_date(current_items)
        recent_three_count = len(_items_since(current_items, latest_date, days=3))
        latest_day_count = len(_items_on_date(current_items, latest_date))
        latest_day_items = _items_on_date(current_items, latest_date)
        latest_day_added = _items_on_date(added, latest_date)
        latest_day_items_block = "\n".join(_format_item(item) for item in latest_day_items) or "（無最近新增）"
        focused_added_block = "\n".join(_format_item(item) for item in focused_added) or "（無符合關注條件的新增）"

        prompt = f"""你是網站更新通知摘要 Agent。
請根據以下結構化列表差異，輸出繁體中文通知。只根據提供內容，不要臆測。

【站點】{site_name}
【區塊】{section_name}
【使用者想追蹤的重點】{watch_description or "未指定"}
【優先關鍵詞】{', '.join(focus_keywords) if focus_keywords else '未指定'}
【目前總筆數】{total_records or "未知"}
【最新日期】{latest_date.isoformat() if latest_date else "未知"}
【近三日新聞數】{recent_three_count}
【今日新增總數】{latest_day_count}

【新增項目】
{added_block}

【最近新增項目（請優先 highlight）】
{latest_day_items_block}

【符合使用者關注重點的新增項目】
{focused_added_block}

請輸出：
1. 第一行：{site_name}更新｜{section_name}
2. 第二、三行必須逐字為「近三日共更新：N 則新聞」與「今日新增：N則」（嚴禁改寫成「近一日」等別稱），不要輸出目前總筆數。
3. 若有符合使用者關注重點的新增項目，優先以「關注重點新增」列出，聚焦法規、公告、澄清、公告送達或 watch_description 指向的資訊，不要被其他一般新聞分散。
4. 接著以「最近新增」列出最新日期當天最多 5 則新聞，保留日期與標題。
5. 不要輸出任何移除項目、移除數量、關注條件或內部判斷文字。
5. 最多 800 字，純文字，不使用 Markdown 標題。
"""
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


