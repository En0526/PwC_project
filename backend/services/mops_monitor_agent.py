"""Agent 1 - MOPS 首頁即時重大資訊列表監控。"""
from __future__ import annotations

import re
import warnings
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

MOPS_HOST = "mops.twse.com.tw"
MOPS_REALTIME_INFO_PATH = "/mops/web/t05sr01_1"
MOPS_REALTIME_INFO_ROUTE = "/web/t05sr01_1"
MOPS_HOME_ROUTE = "/web/home"
MOPS_REALTIME_API_URL = "https://mops.twse.com.tw/mops/api/home_page/t05sr01_1"


def is_mops_realtime_url(url: str) -> bool:
    """Check if URL is MOPS 即時重大資訊 page."""
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if not host.endswith(MOPS_HOST):
        return False
    path = (parsed.path or "").lower()
    fragment = (parsed.fragment or "").lower()
    return (
        MOPS_REALTIME_INFO_PATH in path
        or MOPS_REALTIME_INFO_ROUTE in fragment
        or MOPS_HOME_ROUTE in fragment
    )


def fetch_mops_realtime_structured(count: int = 0, market_kind: str = "") -> dict:
    """Fetch MOPS 即時重大資訊 from the Vue app JSON API."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://mops.twse.com.tw",
        "Referer": "https://mops.twse.com.tw/mops/#/web/t05sr01_1",
    }
    payload = {"count": count, "marketKind": market_kind}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsecureRequestWarning)
        response = requests.post(
            MOPS_REALTIME_API_URL,
            headers=headers,
            json=payload,
            timeout=20,
            verify=False,
        )
    response.raise_for_status()
    data = response.json()
    rows = ((data.get("result") or {}).get("data") or []) if isinstance(data, dict) else []

    items: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        company_code = _clean_text(str(row.get("companyId") or ""))
        company_name = _clean_text(str(row.get("companyAbbreviation") or ""))
        date_text = _normalize_mops_date(str(row.get("date") or ""))
        time_text = _clean_text(str(row.get("time") or ""))
        title = _clean_text(str(row.get("subject") or ""))
        detail_url = _mops_detail_url(row.get("url"))
        if not company_code or not title:
            continue
        publish_time = " ".join(part for part in [date_text, time_text] if part)
        item_key = f"{company_code}|{publish_time}|{title}"
        if item_key in seen_keys:
            continue
        seen_keys.add(item_key)
        items.append(
            {
                "code": company_code,
                "company": company_name,
                "time": publish_time,
                "title": title,
                "url": detail_url,
            }
        )

    return {
        "site_name": "公開資訊觀測站 MOPS",
        "section_name": "首頁 > 即時重大資訊",
        "source_url": "https://mops.twse.com.tw/mops/#/web/t05sr01_1",
        "items": items[:50],
        "datetime": data.get("datetime", "") if isinstance(data, dict) else "",
    }


def extract_mops_structured(html: str, source_url: str) -> dict:
    """解析 MOPS 首頁『即時重大資訊』表格（公司代碼/名稱/發布時間/標題/連結）。"""
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, str]] = []
    seen_keys: set[str] = set()

    # 尋找主要資訊表格
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue

            # 跳過表頭
            if any(cell.name == "th" for cell in cells):
                continue

            # 提取公司代碼
            company_code = _clean_text(cells[0].get_text(" ", strip=True))
            if not company_code or not re.match(r"^\d+$", company_code):
                continue

            # 提取公司簡稱
            company_name = _clean_text(cells[1].get_text(" ", strip=True))
            if not company_name:
                continue

            # 提取發布時間
            publish_time = _clean_text(cells[2].get_text(" ", strip=True))
            if not publish_time:
                continue

            # 提取標題與連結
            title = ""
            url = ""
            if len(cells) > 3:
                link = cells[3].find("a", href=True)
                if link:
                    title = _clean_text(link.get_text(" ", strip=True))
                    href = link.get("href", "").strip()
                    if href:
                        url = urljoin(source_url, href)
                else:
                    title = _clean_text(cells[3].get_text(" ", strip=True))

            if not title:
                continue

            # 去重
            item_key = f"{company_code}|{publish_time}|{title}"
            if item_key in seen_keys:
                continue
            seen_keys.add(item_key)

            items.append(
                {
                    "code": company_code,
                    "company": company_name,
                    "time": publish_time,
                    "title": title,
                    "url": url,
                }
            )

    if not items:
        # 備用方案：尋找任何包含時間格式的表格行
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            company_code = _clean_text(cells[0].get_text(" ", strip=True))
            if not company_code or not re.match(r"^\d+$", company_code):
                continue

            company_name = _clean_text(cells[1].get_text(" ", strip=True))
            time_str = _clean_text(cells[2].get_text(" ", strip=True))

            # 驗證時間格式
            if not re.search(r"\d{2,4}[/-]\d{2}[/-]\d{2}\s+\d{2}:\d{2}", time_str):
                continue

            title = ""
            url = ""
            if len(cells) > 3:
                link = cells[3].find("a", href=True)
                if link:
                    title = _clean_text(link.get_text(" ", strip=True))
                    href = link.get("href", "").strip()
                    if href:
                        url = urljoin(source_url, href)
                else:
                    title = _clean_text(cells[3].get_text(" ", strip=True))

            if title:
                item_key = f"{company_code}|{time_str}|{title}"
                if item_key not in seen_keys:
                    seen_keys.add(item_key)
                    items.append(
                        {
                            "code": company_code,
                            "company": company_name,
                            "time": time_str,
                            "title": title,
                            "url": url,
                        }
                    )

    return {
        "site_name": "公開資訊觀測站 MOPS",
        "section_name": "首頁 > 即時重大資訊",
        "source_url": source_url,
        "items": items[:50],  # 保留最多 50 筆
    }


def mops_snapshot_text(data: dict) -> str:
    """Convert structured data to snapshot text format."""
    lines = [
        "[站點] 公開資訊觀測站 MOPS",
        "[區塊] 首頁 > 即時重大資訊",
        f"[來源] {data.get('source_url', '')}",
        f"[筆數] {len(data.get('items', []))}",
        "[即時資訊列表]",
    ]

    for item in data.get("items", []):
        line_parts = [
            f"[{item['code']}]",
            item["company"],
            item["time"],
            item["title"],
        ]
        if item.get("url"):
            line_parts.append(item["url"])
        lines.append(" | ".join(line_parts))

    return "\n".join(lines)


def _normalize_mops_date(value: str) -> str:
    """Convert ROC date like 115/04/30 to 2026/04/30."""
    match = re.fullmatch(r"\s*(\d{2,3})/(\d{1,2})/(\d{1,2})\s*", value or "")
    if not match:
        return _clean_text(value)
    year = int(match.group(1)) + 1911
    month = int(match.group(2))
    day = int(match.group(3))
    return f"{year:04d}/{month:02d}/{day:02d}"


def _mops_detail_url(raw_url) -> str:
    if not isinstance(raw_url, dict):
        return ""
    api_name = raw_url.get("apiName") or ""
    params = raw_url.get("parameters") or {}
    if not api_name or not isinstance(params, dict):
        return ""
    query = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
    return f"https://mops.twse.com.tw/mops/#/web/{api_name}?{query}"


def _clean_text(text: str) -> str:
    """Clean whitespace and normalize text."""
    return " ".join(text.split())
