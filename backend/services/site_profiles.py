"""Known-site parsers that turn page sections into stable snapshots."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class SectionSnapshot:
    site_name: str
    section_name: str
    source_url: str
    text: str
    confidence: float = 0.9


MOF_NEWS_PATH_ID = "384fb3077bb349ea973e7fc6f13b6974"
MOEA_NEWS_PATH = "/mns/populace/news/news.aspx"
MOEA_NEWS_KIND_TO_SECTION = {
    "1": "本部新聞",
    "9": "即時新聞澄清",
}


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

    if host.endswith("moea.gov.tw") and (parsed.path or "").lower() == MOEA_NEWS_PATH:
        return extract_moea_news_snapshot(
            url=url,
            html=html,
            full_text=full_text,
            watch_description=watch_description,
        )

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


def extract_moea_news_snapshot(
    *,
    url: str,
    html: str,
    full_text: str,
    watch_description: str | None = None,
) -> SectionSnapshot | None:
    """Extract Ministry of Economic Affairs news list rows from the stable news table."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="holderContent_grdNews")
    if table is None:
        return None

    section_leaf = (
        _extract_moea_section_name(soup, watch_description)
        or _extract_moea_section_name_from_url(url)
        or "本部新聞"
    )
    items: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for row in table.find_all("tr"):
        link = row.find("a", id=lambda value: value and "lnkTitle" in value, href=True)
        if not link:
            continue

        title = _clean_text(link.get_text(" ", strip=True))
        href = urljoin(url, link.get("href", "").strip())
        published_at = _extract_moea_row_date(row)
        org_name = _clean_text(_first_text(row, "span", class_="org-name"))
        time_text = _extract_moea_row_time(row)
        if not title or not href or not published_at:
            continue
        if href in seen_urls:
            continue

        seen_urls.add(href)
        title_parts = [title]
        if org_name or time_text:
            meta = " ".join(part for part in [org_name, time_text] if part)
            title_parts.append(f"（{meta}）")

        items.append({
            "published_at": published_at,
            "title": "".join(title_parts),
            "url": href,
        })

    if not items:
        return None

    total_records = _extract_moea_total_records(full_text)
    lines = [
        "[站點] 經濟部",
        f"[區塊] 新聞與公告 > {section_leaf}",
        f"[來源] {url}",
    ]
    if total_records:
        lines.append(f"[總筆數] {total_records}")
    lines.append("[新聞列表]")
    for item in items:
        lines.append(f"  [{item['published_at']}] {item['title']} | {item['url']}")

    return SectionSnapshot(
        site_name="經濟部",
        section_name=f"新聞與公告 > {section_leaf}",
        source_url=url,
        text="\n".join(lines),
        confidence=0.97,
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


def _extract_moea_section_name(soup: BeautifulSoup, watch_description: str | None) -> str:
    heading = soup.find(["h1", "h2", "h3"], string=lambda text: text and _clean_text(text) in {"本部新聞", "即時新聞澄清"})
    if heading:
        return _clean_text(heading.get_text(" ", strip=True))

    watch_text = _clean_text(watch_description or "")
    if "即時新聞澄清" in watch_text:
        return "即時新聞澄清"
    return ""


def _extract_moea_section_name_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    kind = parse_qs(parsed.query or "").get("kind", [""])[0]
    return MOEA_NEWS_KIND_TO_SECTION.get(kind, "")


def _extract_moea_row_date(row) -> str:
    year = _first_text(row, "span", class_="begin-date-yy")
    month = _first_text(row, "span", class_="begin-date-mm")
    day = _first_text(row, "span", class_="begin-date-dd")
    if year and month and day:
        month_digits = re.sub(r"\D", "", month)
        day_digits = re.sub(r"\D", "", day)
        if len(year) == 4 and month_digits and day_digits:
            return f"{year}-{int(month_digits):02d}-{int(day_digits):02d}"

    for span in row.find_all("span", class_="begin-date-time"):
        text = _clean_text(span.get_text(" ", strip=True))
        match = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", text)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return ""


def _extract_moea_row_time(row) -> str:
    for span in row.find_all("span", class_="begin-date-time"):
        text = _clean_text(span.get_text(" ", strip=True))
        if re.fullmatch(r"\d{1,2}:\d{2}", text):
            return text
    return ""


def _extract_moea_total_records(full_text: str) -> str:
    match = re.search(r"目前總共有\s*([\d,]+)\s*筆資料", full_text or "")
    return match.group(1).replace(",", "") if match else ""


def _first_text(node, tag_name: str, **kwargs) -> str:
    found = node.find(tag_name, **kwargs)
    return _clean_text(found.get_text(" ", strip=True)) if found else ""


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())
