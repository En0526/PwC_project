"""Agent 1 - Bingo Bingo 開獎表格監控。"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

BINGO_LATEST_DATA_URL = "https://lotto.auzo.tw/cache/app/latest_bingobingo.cah"


def is_bingo_bingo_url(url: str) -> bool:
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    return host.endswith("lotto.auzo.tw") and "bingobingo.php" in path


def extract_bingo_bingo_structured(html: str, source_url: str) -> dict:
    # 優先走官方前端使用的即時資料端點（JSONP），穩定且即時。
    latest = _fetch_latest_bingo_item()
    if latest:
        return {
            "site_name": "Bingo Bingo 賓果賓果",
            "section_name": "開獎號碼查詢",
            "source_url": source_url,
            "items": [latest],
        }

    # fallback：若即時端點失敗才嘗試從 HTML 解析
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in soup.find_all("tr"):
        text = row.get_text(" ", strip=True)
        if not text:
            continue

        issue = ""
        issue_match = re.search(r"\b(\d{9})\b", text)
        if issue_match:
            issue = issue_match.group(1)
        if not issue:
            continue

        time_match = re.search(r"\b(\d{1,2}:\d{2})\b", text)
        draw_time = time_match.group(1) if time_match else ""

        nums = re.findall(r"\b(\d{1,2})\b", text)
        # 去掉期數中的數字，只留球號（通常會有 >= 20 顆）
        filtered_nums = [n.zfill(2) for n in nums if n != issue and n != draw_time.replace(":", "")]
        if len(filtered_nums) < 20:
            continue
        numbers = filtered_nums[:20]

        key = f"{issue}|{','.join(numbers)}"
        if key in seen:
            continue
        seen.add(key)

        items.append(
            {
                "issue": issue,
                "time": draw_time,
                "numbers": " ".join(numbers),
            }
        )

    return {
        "site_name": "Bingo Bingo 賓果賓果",
        "section_name": "開獎號碼查詢",
        "source_url": source_url,
        "items": items[:30],
    }


def _fetch_latest_bingo_item() -> dict[str, str] | None:
    try:
        resp = requests.get(
            BINGO_LATEST_DATA_URL,
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        raw = (resp.text or "").strip()
        match = re.search(r"jsonp\((\{.*\})\)\s*;?\s*$", raw, flags=re.S)
        if not match:
            return None
        data = json.loads(match.group(1))
        period = str(data.get("Period") or "").strip()
        drawball = str(data.get("Drawball") or "").strip()
        drawdate = str(data.get("Drawdate") or "").strip()
        if not period or not drawball:
            return None
        numbers = [x.strip().zfill(2) for x in drawball.split(",") if x.strip()]
        time_match = re.search(r"(\d{1,2}:\d{2})", drawdate)
        draw_time = time_match.group(1) if time_match else ""
        return {
            "issue": period,
            "time": draw_time,
            "numbers": " ".join(numbers[:20]),
        }
    except Exception:
        return None


def bingo_bingo_snapshot_text(data: dict) -> str:
    lines = [
        f"[站點] {data.get('site_name', 'Bingo Bingo 賓果賓果')}",
        f"[區塊] {data.get('section_name', '開獎號碼查詢')}",
        f"[來源] {data.get('source_url', '')}",
        f"[筆數] {len(data.get('items', []))}",
        "[開獎列表]",
    ]
    for item in data.get("items", []):
        lines.append(f"[{item.get('issue', '')}] {item.get('time', '')} | {item.get('numbers', '')}".strip())
    return "\n".join(lines)
