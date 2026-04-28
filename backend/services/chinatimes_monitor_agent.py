"""Agent 1 - 中時首頁即時新聞列表判讀。"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

from bs4 import BeautifulSoup

CHINATIMES_HOST = "chinatimes.com"


def is_chinatimes_home_url(url: str) -> bool:
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if not host.endswith(CHINATIMES_HOST):
        return False
    path = (parsed.path or "/").strip()
    return path in ("", "/")


def extract_chinatimes_structured(html: str, source_url: str) -> dict:
    """解析首頁『即時新聞』區塊（時間/分類/標題/連結）。"""
    soup = BeautifulSoup(html, "html.parser")
    section = _find_realtime_section(soup)
    items: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    if section is not None:
        for link in section.find_all("a", href=True):
            title = _clean_text(link.get_text(" ", strip=True))
            if not title or len(title) < 8:
                continue

            row_text = _clean_text(link.find_parent().get_text(" ", strip=True) if link.find_parent() else "")
            time_text = _extract_time(row_text)
            category = _extract_category(row_text)
            href = _canonical_news_url(urljoin(source_url, link.get("href", "").strip()))

            if not time_text:
                continue
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append(
                {
                    "time": time_text,
                    "category": category,
                    "title": title,
                    "url": href,
                }
            )

    if not items:
        for link in soup.find_all("a", href=True):
            href_raw = (link.get("href") or "").strip()
            if "/realtimenews/" not in href_raw:
                continue
            title = _clean_text(link.get_text(" ", strip=True))
            if not title or len(title) < 8:
                continue
            context = _ancestor_text(link, levels=4)
            time_text = _extract_time(context)
            if not time_text:
                continue
            category = _extract_category(context)
            href = _canonical_news_url(urljoin(source_url, href_raw))
            if href in seen_urls:
                continue
            seen_urls.add(href)
            items.append({"time": time_text, "category": category, "title": title, "url": href})

    return {
        "site_name": "中時新聞網",
        "section_name": "首頁 > 即時新聞",
        "source_url": source_url,
        "items": items[:30],
    }


def chinatimes_snapshot_text(data: dict) -> str:
    lines = [
        f"[站點] {data.get('site_name') or '中時新聞網'}",
        f"[區塊] {data.get('section_name') or '首頁 > 即時新聞'}",
        f"[來源] {data.get('source_url') or ''}",
        "[新聞列表]",
    ]
    for item in data.get("items", []):
        lines.append(
            f"  [{item.get('time', '')}] {item.get('category', '')} | {item.get('title', '')} | {item.get('url', '')}"
        )
    return "\n".join(lines)


def _find_realtime_section(soup: BeautifulSoup):
    heading = soup.find(string=re.compile(r"即時新聞"))
    if heading is not None:
        node = heading.parent
        for _ in range(6):
            if node is None:
                break
            links = node.find_all("a", href=True)
            if len(links) >= 6:
                return node
            node = node.parent
    tab = soup.find(string=re.compile(r"即時"))
    if tab is not None:
        node = tab.parent
        for _ in range(6):
            if node is None:
                break
            links = node.find_all("a", href=True)
            if len(links) >= 6:
                return node
            node = node.parent
    return soup


def _extract_time(text: str) -> str:
    m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    return f"{m.group(1).zfill(2)}:{m.group(2)}" if m else ""


def _extract_category(text: str) -> str:
    categories = [
        "政治",
        "生活",
        "社會",
        "娛樂",
        "體育",
        "財經",
        "國際",
        "兩岸",
        "科技",
        "軍事",
        "健康",
    ]
    for c in categories:
        if c in text:
            return c
    return "即時"


def _ancestor_text(node, levels: int = 4) -> str:
    cur = node
    for _ in range(max(1, levels)):
        if cur is None:
            break
        blob = _clean_text(cur.get_text(" ", strip=True))
        if _extract_time(blob):
            return blob
        cur = cur.parent
    return _clean_text(node.get_text(" ", strip=True))


def _canonical_news_url(url: str) -> str:
    """移除中時追蹤參數，避免同一新聞被重複收錄。"""
    try:
        sp = urlsplit(url or "")
        if "/realtimenews/" in (sp.path or ""):
            return urlunsplit((sp.scheme, sp.netloc, sp.path, "", ""))
        return url
    except Exception:
        return url


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())
