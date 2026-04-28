"""Known-site parsers that turn page sections into stable snapshots."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class SectionSnapshot:
    site_name: str
    section_name: str
    source_url: str
    text: str
    confidence: float = 0.9


MOF_NEWS_PATH_ID = "384fb3077bb349ea973e7fc6f13b6974"


def extract_known_section_snapshot(
    *,
    url: str,
    html: str,
    full_text: str,
    watch_description: str | None = None,
) -> SectionSnapshot | None:
    """Route known sites to deterministic section parsers."""
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()

    if host.endswith("mof.gov.tw") and MOF_NEWS_PATH_ID in (parsed.path or ""):
        return extract_mof_news_snapshot(url=url, html=html, full_text=full_text)

    return None


def extract_mof_news_snapshot(*, url: str, html: str, full_text: str) -> SectionSnapshot | None:
    """Extract Ministry of Finance '本部新聞' list rows from the first page."""
    soup = BeautifulSoup(html, "html.parser")
    table = _find_mof_news_table(soup)
    if table is None:
        return None

    items: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        if cells[0].name == "th":
            continue

        link = cells[1].find("a", href=True)
        if not link:
            continue

        title = _clean_text(link.get_text(" ", strip=True))
        href = urljoin(url, link.get("href", "").strip())
        published_at = _clean_text(cells[2].get_text(" ", strip=True))
        if not title or not href or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published_at):
            continue
        if href in seen_urls:
            continue

        seen_urls.add(href)
        items.append({"published_at": published_at, "title": title, "url": href})

    if not items:
        return None

    total_pages, total_records = _extract_mof_totals(full_text)
    lines = [
        "[站點] 財政部全球資訊網",
        "[區塊] 新聞與公告 > 本部新聞",
        f"[來源] {url}",
    ]
    if total_pages:
        lines.append(f"[總頁數] {total_pages}")
    if total_records:
        lines.append(f"[總筆數] {total_records}")
    lines.append("[新聞列表]")
    for item in items:
        lines.append(f"  [{item['published_at']}] {item['title']} | {item['url']}")

    return SectionSnapshot(
        site_name="財政部全球資訊網",
        section_name="新聞與公告 > 本部新聞",
        source_url=url,
        text="\n".join(lines),
        confidence=0.95,
    )


def _find_mof_news_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        headers = [_clean_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
        if {"序號", "標題", "發布日期"}.issubset(set(headers)):
            return table
    table = soup.find("table", class_=lambda value: value and "table-list" in value)
    return table


def _extract_mof_totals(full_text: str) -> tuple[str, str]:
    match = re.search(r"總共\s*([\d,]+)\s*頁[，,]\s*([\d,]+)\s*筆資料", full_text or "")
    if not match:
        return "", ""
    return match.group(1).replace(",", ""), match.group(2).replace(",", "")


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())
