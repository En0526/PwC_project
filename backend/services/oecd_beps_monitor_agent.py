"""Agent 1 - OECD BEPS 主題頁面「Latest insights」與「Related publications」區塊判讀。

目標頁面：https://www.oecd.org/en/topics/base-erosion-and-profit-shifting-beps.html
監控兩個區塊：
  1. Latest insights   (公告 / 新聞稿)
  2. Related publications (報告出版品)
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

OECD_HOST = "www.oecd.org"
OECD_BEPS_PATH_FRAGMENT = "base-erosion-and-profit-shifting-beps"
OECD_BASE = "https://www.oecd.org"

SECTION_INSIGHTS = "Latest insights"
SECTION_PUBLICATIONS = "Related publications"


def is_oecd_beps_url(url: str) -> bool:
    """判斷是否為 OECD BEPS 主題頁面。"""
    try:
        parsed = urlparse(url or "")
        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()
        return host == OECD_HOST and OECD_BEPS_PATH_FRAGMENT in path
    except Exception:
        return False


def extract_oecd_beps_structured(html: str, source_url: str) -> dict:
    """解析 OECD BEPS 頁面的 Latest insights 與 Related publications 區塊。

    回傳格式：
    {
        "site_name": "OECD BEPS",
        "source_url": str,
        "sections": {
            "Latest insights": [
                {"date": str, "tag": str, "title": str, "url": str},
                ...
            ],
            "Related publications": [
                {"date": str, "tag": str, "title": str, "subtitle": str, "pages": str, "url": str},
                ...
            ],
        }
    }
    """
    soup = BeautifulSoup(html, "html.parser")

    def _extract_items(section_id: str) -> list[dict]:
        heading = soup.find(id=section_id)
        if not heading:
            return []
        # 往上爬找到含 cmp-list__item 的最近祖先（即卡片輪播容器）
        node = heading
        for _ in range(12):
            node = node.find_parent()
            if node is None:
                break
            items = node.find_all("li", class_="cmp-list__item")
            if items:
                return items
        return []

    def _parse_item(li, include_publication_fields: bool = False) -> dict | None:
        title_el = li.find(class_="card__title-link")
        if not title_el:
            return None
        title = _clean(title_el.get_text(strip=True))
        if not title:
            return None
        href = (title_el.get("href") or "").strip()
        if href and not href.startswith("http"):
            href = OECD_BASE + href

        date_el = li.find(class_="card__date")
        tag_el = li.find(class_="card__tags")
        date = _clean(date_el.get_text(strip=True)) if date_el else ""
        tag = _clean(tag_el.get_text(strip=True)) if tag_el else ""

        result: dict = {"date": date, "tag": tag, "title": title, "url": href}

        if include_publication_fields:
            subtitle_el = li.find(class_="card__subtitle")
            pages_el = li.find(class_="card__pages")
            result["subtitle"] = _clean(subtitle_el.get_text(strip=True)) if subtitle_el else ""
            result["pages"] = _clean(pages_el.get_text(strip=True)) if pages_el else ""

        return result

    insights_lis = _extract_items("latest-insights")
    publications_lis = _extract_items("related-publications")

    insights_items = [r for li in insights_lis if (r := _parse_item(li, False)) is not None]
    publication_items = [r for li in publications_lis if (r := _parse_item(li, True)) is not None]

    return {
        "site_name": "OECD BEPS",
        "source_url": source_url,
        "sections": {
            SECTION_INSIGHTS: insights_items,
            SECTION_PUBLICATIONS: publication_items,
        },
    }


def oecd_beps_snapshot_text(data: dict) -> str:
    """將結構化資料轉為可比對的文字快照。"""
    lines = [
        f"[站點] {data.get('site_name') or 'OECD BEPS'}",
        f"[來源] {data.get('source_url') or ''}",
    ]
    sections: dict = data.get("sections", {})
    for section_name, items in sections.items():
        lines.append(f"[區塊:{section_name}]")
        for item in items:
            date = item.get("date", "")
            tag = item.get("tag", "")
            title = item.get("title", "")
            url = item.get("url", "")
            subtitle = item.get("subtitle", "")
            pages = item.get("pages", "")
            extras = " | ".join(part for part in (subtitle, pages) if part)
            if extras:
                lines.append(f"  [{date}][{tag}] {title} | {extras} | {url}")
            else:
                lines.append(f"  [{date}][{tag}] {title} | {url}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 解析輔助
# ---------------------------------------------------------------------------

def parse_oecd_beps_snapshot(snapshot: str) -> dict[str, list[dict]]:
    """從快照文字還原每個區塊的項目列表，供 diff 使用。"""
    sections: dict[str, list[dict]] = {}
    current_section: str | None = None

    for line in snapshot.splitlines():
        s = line.strip()
        m = re.match(r"^\[區塊:(.+?)\]$", s)
        if m:
            current_section = m.group(1)
            sections[current_section] = []
            continue
        if current_section is None:
            continue
        # 格式：  [date][tag] title | (extras |) url
        m2 = re.match(r"^\[(.+?)\]\[(.+?)\]\s+(.+?)\s+\|\s+(.+)$", s)
        if not m2:
            continue
        date, tag, rest, last = m2.group(1), m2.group(2), m2.group(3), m2.group(4)
        # last 可能是 "subtitle | pages | url" 或 "pages | url" 或 "url"
        parts = [p.strip() for p in last.split(" | ")]
        # 最後一個 part 是 URL（包含 oecd.org 或以 / 或 http 開頭）
        if parts and (parts[-1].startswith("http") or parts[-1].startswith("/")):
            url = parts[-1]
            extras = parts[:-1]
        else:
            url = ""
            extras = parts
        item: dict = {
            "date": date,
            "tag": tag,
            "title": rest,
            "url": url,
        }
        if len(extras) == 2:
            item["subtitle"] = extras[0]
            item["pages"] = extras[1]
        elif len(extras) == 1:
            item["pages"] = extras[0]
        sections[current_section].append(item)

    return sections


def _clean(text: str) -> str:
    """清理文字：壓縮空白、移除不可見字元。"""
    text = re.sub(r"[\u00ad\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
