"""Agent 1 - NTBNA 本局新聞稿列表判讀。"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

NTBNA_HOST = "ntbna.gov.tw"
NTBNA_NEWS_PATH_HINT = "/multiplehtml/"


def is_ntbna_news_url(url: str) -> bool:
    low = (url or "").lower()
    return NTBNA_HOST in low and NTBNA_NEWS_PATH_HINT in low


def extract_ntbna_structured(html: str, source_url: str) -> dict:
    """解析本局新聞稿頁面紅框列表區塊。"""
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text("\n", strip=True)

    table = _find_news_table(soup)
    items: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    if table is not None:
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            if cells[0].name == "th":
                continue

            title_cell = cells[1]
            date_cell = cells[2]
            a_tag = title_cell.find("a", href=True)
            title = _clean_text((a_tag.get_text(" ", strip=True) if a_tag else title_cell.get_text(" ", strip=True)))
            date = _normalize_date(date_cell.get_text(" ", strip=True))
            href = urljoin(source_url, (a_tag.get("href", "").strip() if a_tag else ""))

            if not title or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                continue
            if href and href in seen_urls:
                continue
            if href:
                seen_urls.add(href)
            items.append({"date": date, "title": title, "url": href})

    total_pages, total_records = _extract_totals(page_text)
    return {
        "site_name": "財政部北區國稅局",
        "section_name": "公告訊息 > 新聞稿 > 本局新聞稿",
        "source_url": source_url,
        "total_pages": total_pages,
        "total_records": total_records,
        "items": items,
    }


def ntbna_snapshot_text(data: dict) -> str:
    """轉為穩定快照文字，供 hash/diff 使用。"""
    lines = [
        f"[站點] {data.get('site_name') or '財政部北區國稅局'}",
        f"[區塊] {data.get('section_name') or '本局新聞稿'}",
        f"[來源] {data.get('source_url') or ''}",
    ]
    if data.get("total_pages"):
        lines.append(f"[總頁數] {data.get('total_pages')}")
    if data.get("total_records"):
        lines.append(f"[總筆數] {data.get('total_records')}")
    lines.append("[新聞列表]")
    for item in data.get("items", []):
        lines.append(f"  [{item.get('date', '')}] {item.get('title', '')} | {item.get('url', '')}")
    return "\n".join(lines)


def _find_news_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        headers = {_clean_text(th.get_text(" ", strip=True)) for th in table.find_all("th")}
        if {"序號", "標題", "發布日期"}.issubset(headers):
            return table
    return None


def _extract_totals(page_text: str) -> tuple[str, str]:
    match = re.search(r"總共\s*([\d,]+)\s*頁[，,]\s*([\d,]+)\s*筆資料", page_text or "")
    if not match:
        return "", ""
    return match.group(1).replace(",", ""), match.group(2).replace(",", "")


def _normalize_date(text: str) -> str:
    text = _clean_text(text)
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", text)
    if not m:
        return text
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())
