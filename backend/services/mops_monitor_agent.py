"""Agent 1 - MOPS 首頁即時重大資訊列表監控。"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

MOPS_HOST = "mops.twse.com.tw"
MOPS_REALTIME_INFO_PATH = "/mops/web/t05sr01_1"


def is_mops_realtime_url(url: str) -> bool:
    """Check if URL is MOPS 即時重大資訊 page."""
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if not host.endswith(MOPS_HOST):
        return False
    path = (parsed.path or "").lower()
    return MOPS_REALTIME_INFO_PATH in path


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
            line_parts.append(f"| {item['url']}")
        lines.append(" | ".join(line_parts))

    return "\n".join(lines)


def _clean_text(text: str) -> str:
    """Clean whitespace and normalize text."""
    return " ".join(text.split())
