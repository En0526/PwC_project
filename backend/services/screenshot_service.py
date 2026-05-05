from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def capture_page_screenshot(url: str, *, timeout_ms: int = 6000) -> str | None:
    """
    Capture a lightweight screenshot and return web path (e.g. /static/snapshots/xxx.jpg).
    Returns None on any failure.
    """
    try:
        project_root = Path(__file__).resolve().parents[2]
        snapshots_dir = project_root / "frontend" / "static" / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"snapshot_{stamp}.jpg"
        output_path = snapshots_dir / filename

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 768})
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if _is_bingo_url(url):
                if not _capture_bingo_draw_region(page, str(output_path)):
                    page.screenshot(path=str(output_path), full_page=False, type="jpeg", quality=55)
            else:
                page.screenshot(path=str(output_path), full_page=False, type="jpeg", quality=55)
            browser.close()

        return f"/static/snapshots/{filename}"
    except Exception:
        return None


def _is_bingo_url(url: str) -> bool:
    p = urlparse(url or "")
    return (p.hostname or "").lower().endswith("lotto.auzo.tw") and "bingobingo.php" in (p.path or "").lower()


def _capture_bingo_draw_region(page, output_path: str) -> bool:
    """
    優先截取 Bingo 開獎號碼區塊（你提供截圖中的表格位置），
    降低頁面其他區塊干擾。
    """
    try:
        # 這頁真正的開獎主表固定是 #bingotable，且會先顯示「載入中」再由 JS 填入。
        page.wait_for_timeout(1000)
        main_table = page.locator("#bingotable").first
        if not main_table or main_table.count() == 0:
            return False

        # 等待「載入中」消失或列數增加，最多等待約 4 秒。
        for _ in range(8):
            table_text = (main_table.inner_text() or "").strip()
            row_count = page.locator("#bingotable tr").count()
            if "載入中" not in table_text and row_count >= 3:
                break
            page.wait_for_timeout(500)

        main_table.screenshot(path=output_path, type="jpeg", quality=65)
        return True
    except Exception:
        return False
