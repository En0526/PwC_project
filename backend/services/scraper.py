"""擷取網頁內容，並可依使用者描述用 AI 擷取關注區塊。"""
import hashlib
import re
import requests
from bs4 import BeautifulSoup

from backend.services.gemini_service import extract_watch_content

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def fetch_page(url: str, timeout: int = 15) -> tuple[str | None, str | None]:
    """取得網頁 HTML，回傳 (html_text, error_message)。"""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, verify=False)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text, None
    except requests.RequestException as e:
        return None, str(e)


def html_to_clean_text(html: str, max_chars: int = 100_000) -> str:
    """將 HTML 轉成純文字，便於比對與儲存。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars] if len(text) > max_chars else text


def content_hash(text: str) -> str:
    """計算內容雜湊，用於快速判斷是否變更。"""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def scrape_stdtime_clock(url: str, watch_description: str | None) -> str | None:
    """stdtime.gov.tw/WebClock 特殊處理：取 /Home/GetServerTime 的時間值。"""
    if not watch_description:
        return None
    desc = watch_description.lower()
    if "stdtime" not in url.lower() or "webclock" not in url.lower():
        return None
    if "本機時間" in watch_description or "client time" in desc:
        # 只能取得 server time API 近似值，並主動回傳一個時間字串
        api_url = url.split("/home/")[0] + "/Home/GetServerTime"
        page, err = fetch_page(api_url)
        if err or not page:
            return None
        # API 回傳範例："2026-04-03T14:20:11.9622285+08:00"
        return f"ServerTime: {page.strip().strip('"')}"
    return None


def scrape_and_extract(
    url: str,
    watch_description: str | None,
    use_gemini: bool = True,
    gemini_api_key: str = "",
) -> tuple[str, str]:
    """
    擷取網頁並依使用者描述取出「要觀看」的內容。
    若 watch_description 為空則回傳整頁純文字。
    回傳 (content_text, content_hash)。
    """
    html, err = fetch_page(url)
    if err:
        raise RuntimeError(f"無法取得網頁: {err}")

    full_text = html_to_clean_text(html)
    if not watch_description or not watch_description.strip():
        h = content_hash(full_text)
        return full_text, h

    # 先嘗試特殊網站的文字擷取，避免 JS 動態內容導致抓不到差異
    st_text = scrape_stdtime_clock(url, watch_description)
    if st_text:
        h = content_hash(st_text)
        return st_text, h

    if use_gemini and gemini_api_key:
        try:
            extracted = extract_watch_content(
                html=html[:100_000],
                full_text=full_text[:50_000],
                watch_description=watch_description.strip(),
                api_key=gemini_api_key,
            )
            if extracted:
                h = content_hash(extracted)
                return extracted, h
        except Exception:
            pass  # 失敗時 fallback 到全文

    # 無 AI 或失敗：回傳全文
    h = content_hash(full_text)
    return full_text, h
