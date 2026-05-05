"""Agent 2 - Bingo Bingo 開獎差異判讀與摘要。"""
from __future__ import annotations

import re


def generate_bingo_diff_report(
    *,
    previous_snapshot: str | None,
    current_snapshot: str,
) -> str | None:
    curr = _extract_items(current_snapshot)
    prev = _extract_items(previous_snapshot)
    if not curr:
        return None

    prev_keys = {_item_key(x) for x in prev}
    added = [x for x in curr if _item_key(x) not in prev_keys]
    if not added and previous_snapshot:
        return None

    lines = [
        "Bingo Bingo 開獎更新｜開獎號碼查詢",
        f"本次新增期數：{len(added)} 期",
        "-" * 32,
    ]
    if added:
        lines.append("最新新增：")
        for i, item in enumerate(added[:5], 1):
            lines.append(f"  {i}. 第 {item['issue']} 期 {item['time']}：{item['numbers']}")
    else:
        lines.append("首次建立監測基準，尚未可比較新增期數。")
        if curr:
            latest = curr[0]
            lines.append(f"最新一期：第 {latest['issue']} 期 {latest['time']}：{latest['numbers']}")
    return "\n".join(lines)


def _extract_items(snapshot: str | None) -> list[dict[str, str]]:
    if not snapshot:
        return []
    items: list[dict[str, str]] = []
    in_list = False
    for line in snapshot.splitlines():
        s = line.strip()
        if s == "[開獎列表]":
            in_list = True
            continue
        if in_list and s.startswith("[") and not re.match(r"^\[\d{9}\]", s):
            break
        m = re.match(r"^\[(\d{9})\]\s+(\d{1,2}:\d{2})\s+\|\s+(.+)$", s)
        if not m:
            continue
        items.append(
            {
                "issue": m.group(1),
                "time": m.group(2),
                "numbers": m.group(3).strip(),
            }
        )
    return items


def _item_key(item: dict[str, str]) -> str:
    return f"{item.get('issue', '')}|{item.get('numbers', '')}"
