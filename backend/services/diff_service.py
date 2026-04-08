"""比對兩段文字差異，產生人類可讀的差異說明。"""
from diff_match_patch import diff_match_patch


def compute_diff(old_text: str, new_text: str) -> list[tuple[int, str]]:
    """
    比對 old_text 與 new_text，回傳 diff 列表： (operation, text)
    operation: -1 刪除, 0 不變, 1 新增
    """
    dmp = diff_match_patch()
    diffs = dmp.diff_main(old_text, new_text)
    dmp.diff_cleanupSemantic(diffs)
    return [(op, text) for op, text in diffs]


def diff_to_summary(old_text: str, new_text: str, max_snippets: int = 5) -> str:
    """
    產生簡短差異摘要，適合通知內容。
    列出幾段「新增」或「刪除」的片段。
    """
    diffs = compute_diff(old_text, new_text)
    added = []
    removed = []
    for op, text in diffs:
        t = text.strip()
        if not t or len(t) < 3:
            continue
        if op == 1:
            added.append(t[:500])
        elif op == -1:
            removed.append(t[:500])

    lines = []
    if added:
        lines.append("【新增／變更】")
        for s in added[:max_snippets]:
            lines.append(s[:200] + ("..." if len(s) > 200 else ""))
    if removed:
        lines.append("【移除】")
        for s in removed[:max_snippets]:
            lines.append(s[:200] + ("..." if len(s) > 200 else ""))
    if not lines:
        # 檢查是否有任何差異
        total_changes = sum(len(text) for op, text in diffs if op != 0)
        if total_changes > 0:
            return f"內容有變更（{total_changes} 字元差異），但可能是格式或小幅修改。"
        else:
            return "內容完全相同，無差異。"
    return "\n".join(lines)
