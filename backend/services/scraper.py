"""擷取網頁內容，並可依使用者描述用 AI 擷取關注區塊。"""
import hashlib
import os
import re
import ssl
import warnings
from urllib.parse import urlparse, urlunparse
import requests
from bs4 import BeautifulSoup

from backend.services.gemini_service import extract_watch_content

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _get_insecure_ssl_domains() -> set[str]:
    # 內建已知憑證異常站台（可再由 .env 擴充）
    domains = {"www.ardf.org.tw", "law.moj.gov.tw"}
    raw = (os.environ.get("INSECURE_SSL_DOMAINS") or "").strip()
    if raw:
        domains.update({x.strip().lower() for x in raw.split(",") if x.strip()})
    return domains


def _is_insecure_ssl_allowed(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in _get_insecure_ssl_domains()


def fetch_page(url: str, timeout: int = 20) -> tuple[str | None, str | None]:
    """取得網頁 HTML，回傳 (html_text, error_message)。"""
    normalized_url = normalize_url(url)
    try:
        r = requests.get(normalized_url, headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text, None
    except requests.RequestException as e:
        # 只對白名單網域做 SSL 寬鬆模式 fallback，其他網站仍維持嚴格驗證
        is_ssl_error = isinstance(getattr(e, "reason", None), ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(e)
        if is_ssl_error and _is_insecure_ssl_allowed(normalized_url):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    r = requests.get(normalized_url, headers=DEFAULT_HEADERS, timeout=timeout, verify=False)
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text, None
            except requests.RequestException as e2:
                return None, f"{e2}（已嘗試 SSL 寬鬆模式）"
        return None, str(e)


def normalize_url(url: str) -> str:
    """
    某些站台有舊網域或憑證問題，先做安全的網域正規化。
    - mopsov.twse.com.tw -> mops.twse.com.tw
    """
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower()
        if host == "mopsov.twse.com.tw":
            p = p._replace(netloc="mops.twse.com.tw")
            return urlunparse(p)
        return url
    except Exception:
        return url


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
    if "stdtime" not in url.lower() or "webclock" not in url.lower():
        return None

    # stdtime 的 WebClock 頁面主要用 JS 更新時間，原始 HTML 不一定會有變化。
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    api_url = urlunparse(parsed._replace(path="/Home/GetServerTime", query="", fragment=""))
    page, err = fetch_page(api_url)
    if err or not page:
        return None
    # API 回傳範例："2026-04-03T14:20:11.9622285+08:00"
    return f"ServerTime: {page.strip().strip('"')}"


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

    # 先嘗試特殊網站的文字擷取，避免 JS 動態內容導致抓不到差異
    st_text = scrape_stdtime_clock(url, watch_description)
    if st_text:
        h = content_hash(st_text)
        return st_text, h

    if not watch_description or not watch_description.strip():
        h = content_hash(full_text)
        return full_text, h

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
