"""擷取網頁內容，並可依使用者描述用 AI 擷取關注區塊。"""
import hashlib
import os
import re
import ssl
import warnings
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
except Exception:  # pragma: no cover - optional dependency
    PlaywrightTimeoutError = None
    sync_playwright = None

from backend.services.gemini_service import extract_watch_content
from backend.services.presets import get_presets
from backend.services.stdtime_notify import format_stdtime_snapshot_from_api_body
from backend.services.gazette_monitor_agent import (
    is_gazette_url,
    extract_gazette_structured,
    gazette_snapshot_text,
    analyze_gazette_change,
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


class ScrapeFailure(RuntimeError):
    def __init__(self, code: str, message: str, hint: str = "", retryable: bool = True, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.retryable = retryable
        self.http_status = http_status


def _url_expects_rss(url: str) -> bool:
    """判斷 URL 是否看起來應該提供 RSS/Atom feed（基於 URL 路徑）。"""
    u = (url or "").lower()
    return any(k in u for k in ("/feed", "/rss", "/atom", ".xml"))


def _is_probably_rss(url: str, content_type: str, body: str) -> bool:
    u = (url or "").lower()
    ct = (content_type or "").lower()
    head = (body or "")[:300].lstrip().lower()
    if any(k in u for k in ("/feed", "/rss", "/atom", ".xml")):
        return True
    if any(k in ct for k in ("application/rss+xml", "application/atom+xml", "application/xml", "text/xml")):
        return True
    return head.startswith("<?xml") and ("<rss" in head or "<feed" in head)


def _rss_entry_text(entry: dict) -> str:
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    guid = (entry.get("guid") or "").strip()
    date = (entry.get("date") or "").strip()
    parts = [x for x in (guid, title, date, link) if x]
    return " | ".join(parts)


def detect_rss_feeds(html: str, base_url: str = "") -> list[dict]:
    """從 HTML 中檢測 RSS/Atom feed 鏈接。
    
    返回: [{"url": "...", "title": "...", "type": "rss|atom"}]
    """
    feeds = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # 查找 <link rel="alternate"> 標籤
        for link_tag in soup.find_all("link", rel="alternate"):
            link_type = (link_tag.get("type") or "").lower()
            href = (link_tag.get("href") or "").strip()
            title = (link_tag.get("title") or "").strip()
            
            # 檢查是否為 RSS 或 Atom 類型
            is_rss = "rss" in link_type or "application/rss" in link_type
            is_atom = "atom" in link_type or "application/atom" in link_type
            
            if (is_rss or is_atom) and href:
                # 如果 href 是相對 URL，轉為絕對 URL
                if base_url and not href.startswith("http"):
                    from urllib.parse import urljoin
                    href = urljoin(base_url, href)
                
                feed_type = "atom" if is_atom else "rss"
                feeds.append({
                    "url": href,
                    "title": title or f"{feed_type.upper()} Feed",
                    "type": feed_type,
                })
        
        # 也查找常見的 RSS URL 模式（作為後備）
        if not feeds:
            common_patterns = [
                "/feed", "/rss", "/atom", "/feeds", 
                "/feed.xml", "/rss.xml", "/atom.xml"
            ]
            base_domain = base_url.rsplit("/", 1)[0] if base_url else ""
            for pattern in common_patterns:
                candidate_url = base_domain + pattern if base_domain else None
                if candidate_url:
                    feeds.append({
                        "url": candidate_url,
                        "title": f"RSS Feed ({pattern})",
                        "type": "rss",
                        "is_guess": True,  # 標記為推測，不確定
                    })
        
        return feeds
    except Exception as e:
        return []


def validate_rss_feed(url: str, timeout: int = 10) -> dict:
    """驗證 URL 是否提供有效的 RSS/Atom feed。
    
    返回: {
        "valid": bool,
        "type": "rss" | "atom" | None,
        "items_count": int,
        "title": str,
        "message": str
    }
    """
    try:
        html, content_type = fetch_page_detailed(url, timeout=timeout)
        
        if _is_probably_rss(url, content_type, html):
            try:
                # 嘗試解析 RSS
                root = ET.fromstring(html)
                root_name = _strip_ns(root.tag).lower()
                
                # 判斷類型
                feed_type = None
                item_count = 0
                title = ""
                
                if root_name in ("rss", "rdf"):
                    feed_type = "rss"
                    items = root.findall(".//item")
                    item_count = len(items)
                    title_el = root.find(".//title")
                    if title_el is not None:
                        title = (title_el.text or "").strip()
                
                elif root_name == "feed":
                    feed_type = "atom"
                    ns = {"a": "http://www.w3.org/2005/Atom"}
                    entries = root.findall("a:entry", ns)
                    item_count = len(entries)
                    title_el = root.find("a:title", ns)
                    if title_el is not None:
                        title = (title_el.text or "").strip()
                
                if feed_type:
                    return {
                        "valid": True,
                        "type": feed_type,
                        "items_count": item_count,
                        "title": title,
                        "message": f"✓ 有效的 {feed_type.upper()} feed，包含 {item_count} 項"
                    }
            except ET.ParseError:
                pass
        
        # 不是 RSS 或解析失敗
        return {
            "valid": False,
            "type": None,
            "items_count": 0,
            "title": "",
            "message": "✗ 此 URL 不提供有效的 RSS/Atom feed"
        }
    
    except ScrapeFailure as e:
        return {
            "valid": False,
            "type": None,
            "items_count": 0,
            "title": "",
            "message": f"✗ 無法連線：{e.hint}"
        }
    except Exception as e:
        return {
            "valid": False,
            "type": None,
            "items_count": 0,
            "title": "",
            "message": f"✗ 驗證失敗：{str(e)}"
        }


def _rss_entry_text(entry: dict) -> str:
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    guid = (entry.get("guid") or "").strip()
    date = (entry.get("date") or "").strip()
    parts = [x for x in (guid, title, date, link) if x]
    return " | ".join(parts)


def _strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_rss_snapshot(xml_text: str, max_items: int = 20) -> str:
    """將 RSS / Atom 轉為穩定文字快照，避免誤判。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ScrapeFailure(
            code="rss_parse_failed",
            message=f"RSS 解析失敗: {e}",
            hint="此連結不是有效 RSS/Atom，請改用網站的正式 feed URL。",
            retryable=False,
        )

    root_name = _strip_ns(root.tag).lower()
    entries: list[dict] = []

    if root_name in ("rss", "rdf"):
        for item in root.findall(".//item")[:max_items]:
            entries.append(
                {
                    "title": (item.findtext("title") or "").strip(),
                    "link": (item.findtext("link") or "").strip(),
                    "guid": (item.findtext("guid") or "").strip(),
                    "date": (item.findtext("pubDate") or item.findtext("updated") or "").strip(),
                }
            )
    elif root_name == "feed":
        ns = {"a": "http://www.w3.org/2005/Atom"}
        atom_entries = root.findall("a:entry", ns)
        for item in atom_entries[:max_items]:
            link_el = item.find("a:link", ns)
            link = ""
            if link_el is not None:
                link = (link_el.attrib.get("href") or "").strip()
            entries.append(
                {
                    "title": (item.findtext("a:title", default="", namespaces=ns) or "").strip(),
                    "link": link,
                    "guid": (item.findtext("a:id", default="", namespaces=ns) or "").strip(),
                    "date": (
                        item.findtext("a:updated", default="", namespaces=ns)
                        or item.findtext("a:published", default="", namespaces=ns)
                        or ""
                    ).strip(),
                }
            )
    else:
        raise ScrapeFailure(
            code="rss_parse_failed",
            message="內容看起來是 XML，但不是 RSS/Atom 格式。",
            hint="請確認 feed 連結是否正確，或改用一般網頁監測。",
            retryable=False,
        )

    lines = [_rss_entry_text(entry) for entry in entries if _rss_entry_text(entry)]
    if not lines:
        raise ScrapeFailure(
            code="rss_parse_failed",
            message="RSS 解析成功但找不到 item/entry。",
            hint="此 feed 可能無資料或格式特殊，請改用其他來源。",
            retryable=False,
        )
    return "\n".join(lines)


def _looks_dynamic_unreadable(html: str, text: str) -> bool:
    low_text = len((text or "").strip()) < 120
    h = (html or "").lower()
    dynamic_signals = [
        "enable javascript",
        "please enable javascript",
        "__next_data__",
        "id=\"__next\"",
        "data-reactroot",
        "hydration",
        "webpack",
    ]
    score = sum(1 for k in dynamic_signals if k in h)
    return low_text and score >= 2


def _classify_request_exception(e: requests.RequestException, url: str, used_insecure_ssl: bool = False) -> ScrapeFailure:
    if isinstance(e, requests.Timeout):
        return ScrapeFailure(
            code="timeout",
            message=f"連線逾時: {e}",
            hint="網站回應過慢，建議稍後重試或拉長 timeout。",
            retryable=True,
        )

    if isinstance(e, requests.HTTPError):
        status = e.response.status_code if e.response is not None else None
        if status == 403:
            return ScrapeFailure(
                code="http_403",
                message=f"網站拒絕存取 (HTTP 403): {url}",
                hint="目標站可能啟用反爬機制，建議改用 RSS 或瀏覽器模式。",
                retryable=False,
                http_status=status,
            )
        if status == 429:
            return ScrapeFailure(
                code="http_429",
                message=f"請求過於頻繁 (HTTP 429): {url}",
                hint="請降低檢查頻率，避免被限制。",
                retryable=True,
                http_status=status,
            )
        if status is not None and status >= 500:
            return ScrapeFailure(
                code="http_5xx",
                message=f"伺服器錯誤 (HTTP {status}): {url}",
                hint="網站端暫時異常，稍後重試。",
                retryable=True,
                http_status=status,
            )
        return ScrapeFailure(
            code="http_error",
            message=f"HTTP 錯誤 ({status}): {url}",
            hint="請檢查網址是否可公開存取。",
            retryable=False,
            http_status=status,
        )

    is_ssl_error = isinstance(getattr(e, "reason", None), ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(e)
    if is_ssl_error:
        hint = "網站憑證異常。"
        if used_insecure_ssl:
            hint += " 已嘗試 SSL 寬鬆模式仍失敗。"
        return ScrapeFailure(
            code="ssl_error",
            message=f"SSL 憑證錯誤: {e}",
            hint=hint,
            retryable=False,
        )

    if isinstance(e, requests.ConnectionError):
        return ScrapeFailure(
            code="connection_error",
            message=f"連線失敗: {e}",
            hint="無法建立連線，請檢查網路或目標網站狀態。",
            retryable=True,
        )

    return ScrapeFailure(
        code="request_error",
        message=f"請求失敗: {e}",
        hint="請稍後重試。",
        retryable=True,
    )


def _playwright_enabled() -> bool:
    raw = (os.environ.get("PLAYWRIGHT_FALLBACK_ENABLED") or "1").strip().lower()
    return raw not in ("0", "false", "no")


def fetch_page_playwright(url: str, timeout: int = 20) -> tuple[str, str]:
    """使用 Playwright 抓取頁面（處理 JS 動態載入與部分反爬場景）。"""
    if not _playwright_enabled():
        raise ScrapeFailure(
            code="playwright_disabled",
            message="Playwright fallback 已被停用。",
            hint="可設定 PLAYWRIGHT_FALLBACK_ENABLED=1 啟用瀏覽器模式。",
            retryable=False,
        )
    if sync_playwright is None:
        raise ScrapeFailure(
            code="playwright_unavailable",
            message="未安裝 Playwright。",
            hint="請安裝 playwright 套件並執行 `playwright install chromium`。",
            retryable=False,
        )

    normalized_url = normalize_url(url)
    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT, locale="zh-TW")
            page = context.new_page()
            page.goto(normalized_url, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(1200)
            html = page.content()
            context.close()
            return html, "text/html; charset=utf-8"
    except Exception as e:
        is_pw_timeout = PlaywrightTimeoutError is not None and isinstance(e, PlaywrightTimeoutError)
        if is_pw_timeout:
            raise ScrapeFailure(
                code="playwright_timeout",
                message=f"瀏覽器模式逾時: {e}",
                hint="網站載入過慢，請稍後再試。",
                retryable=True,
            ) from e
        raise ScrapeFailure(
            code="playwright_error",
            message=f"瀏覽器模式失敗: {e}",
            hint="建議確認 Chromium 是否安裝完成，或稍後重試。",
            retryable=True,
        ) from e
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


def _get_insecure_ssl_domains() -> set[str]:
    # 內建已知憑證異常站台（可再由 .env 擴充）
    domains = {"www.ardf.org.tw", "law.moj.gov.tw"}
    # 常用清單中的網站一律視為 SSL 白名單（使用者要求）
    for p in get_presets():
        try:
            host = (urlparse(p.url).hostname or "").lower()
        except Exception:
            host = ""
        if host:
            domains.add(host)
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
    try:
        html_text, _ = fetch_page_detailed(url, timeout=timeout)
        return html_text, None
    except ScrapeFailure as e:
        return None, str(e)


def fetch_page_detailed(url: str, timeout: int = 20) -> tuple[str, str]:
    """取得網頁內容與 content-type，失敗時丟 ScrapeFailure。"""
    normalized_url = normalize_url(url)
    try:
        r = requests.get(normalized_url, headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text, (r.headers.get("Content-Type") or "")
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
                return r.text, (r.headers.get("Content-Type") or "")
            except requests.RequestException as e2:
                raise _classify_request_exception(e2, normalized_url, used_insecure_ssl=True) from e2
        raise _classify_request_exception(e, normalized_url, used_insecure_ssl=False) from e


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
    return format_stdtime_snapshot_from_api_body(page)


def scrape_and_extract(
    url: str,
    watch_description: str | None,
    use_gemini: bool = True,
    gemini_api_key: str = "",
) -> tuple[str, str, dict]:
    """
    擷取網頁並依使用者描述取出「要觀看」的內容。
    若 watch_description 為空則回傳整頁純文字。
    回傳 (content_text, content_hash, diagnostic_info)。
    
    診斷代碼區分：
      - http_403 / http_429 / http_error / timeout: 反爬/網路錯誤
      - rss_not_found: URL 看起來是 RSS，但伺服器返回非 RSS 內容
      - rss_fetch_failed: URL 看起來是 RSS，但 fetch 失敗
      - html_dynamic_unreadable: 返回 HTML 但需要 JS 渲染
      - ok: 成功取得內容
    """
    # 先嘗試特殊網站的文字擷取，避免 JS 動態內容導致抓不到差異
    st_text = scrape_stdtime_clock(url, watch_description)
    if st_text:
        h = content_hash(st_text)
        return st_text, h, {"status": "ok", "source": "stdtime", "confidence": 1.0, "hint": ""}

    # 行政院公報資訊網專屬 Agent 1 處理
    if is_gazette_url(url):
        try:
            html_raw, _ = fetch_page_detailed(url)
            structured = extract_gazette_structured(html_raw)
            snapshot = gazette_snapshot_text(structured)
            h = content_hash(snapshot)
            return snapshot, h, {"status": "ok", "source": "gazette_agent", "confidence": 0.95, "hint": ""}
        except ScrapeFailure:
            raise
        except Exception:
            pass  # 解析失敗時 fallback 到一般流程

    url_expects_rss = _url_expects_rss(url)
    playwright_used = False

    try:
        html, content_type = fetch_page_detailed(url)
    except ScrapeFailure as e:
        # fetch 失敗：判斷是否期望 RSS
        if url_expects_rss:
            # URL 看起來像 RSS，但 fetch 失敗
            # 如果被 403/429 阻擋，也嘗試 Playwright fallback
            if e.code in ("http_403", "http_429"):
                try:
                    html, content_type = fetch_page_playwright(url)
                    playwright_used = True
                except ScrapeFailure as pe:
                    # Playwright 也失敗，回報 RSS 被阻擋的錯誤
                    raise ScrapeFailure(
                        code="rss_fetch_failed_blocked",
                        message=f"無法取得 RSS feed：{e.message}（已嘗試瀏覽器模式）",
                        hint="此 RSS 源被網站反爬嚴格阻擋，建議改為監測主頁面 HTML，或更換 feed 來源。",
                        retryable=False,
                        http_status=e.http_status,
                    ) from e
            elif e.code == "timeout":
                raise ScrapeFailure(
                    code="rss_fetch_failed_timeout",
                    message=f"無法取得 RSS feed：連線逾時",
                    hint="RSS 源伺服器回應太慢，建議稍後重試。",
                    retryable=True,
                ) from e
            else:
                raise ScrapeFailure(
                    code="rss_fetch_failed",
                    message=f"無法取得 RSS feed：{e.message}",
                    hint="無法連線到 RSS 源，請檢查 feed URL 是否正確、網站是否下線。",
                    retryable=True,
                ) from e
        else:
            # URL 不是 RSS：遇到反爬/連線問題時嘗試瀏覽器模式 fallback
            if e.code in ("http_403", "http_429", "timeout", "connection_error", "http_5xx", "http_error", "request_error"):
                try:
                    html, content_type = fetch_page_playwright(url)
                    playwright_used = True
                except ScrapeFailure as pe:
                    raise ScrapeFailure(
                        code=e.code,
                        message=e.message,
                        hint=f"{e.hint}；且瀏覽器模式也失敗（{pe.code}）。",
                        retryable=e.retryable,
                        http_status=e.http_status,
                    ) from e
            else:
                raise e

    # fetch 成功，檢查內容格式
    if _is_probably_rss(url, content_type, html):
        # 內容看起來像 RSS，解析之
        rss_text = parse_rss_snapshot(html)
        h = content_hash(rss_text)
        return rss_text, h, {"status": "ok", "source": "rss", "confidence": 0.95, "hint": ""}
    elif url_expects_rss:
        # URL 看起來像 RSS，但伺服器返回非 RSS 內容（例如 HTML 登入頁、403 頁面等）
        raise ScrapeFailure(
            code="rss_not_found",
            message=f"指定的 RSS 源返回非 RSS 內容（Content-Type: {content_type})。",
            hint="此連結不提供 RSS feed（可能是登入頁、錯誤頁等）。請改用其他 RSS 源，或改為監測網站的一般 HTML 頁面。",
            retryable=False,
        )

    # 內容是 HTML，轉為文本
    full_text = html_to_clean_text(html)

    if _looks_dynamic_unreadable(html, full_text):
        if not playwright_used:
            try:
                html, content_type = fetch_page_playwright(url)
                playwright_used = True
                full_text = html_to_clean_text(html)
            except ScrapeFailure:
                raise ScrapeFailure(
                    code="html_dynamic_unreadable",
                    message="此網站主要內容由 JavaScript 動態載入，無法穩定判讀。",
                    hint="建議改用 RSS，或啟用瀏覽器渲染模式（需安裝 Playwright）。",
                    retryable=False,
                )
        if _looks_dynamic_unreadable(html, full_text):
            raise ScrapeFailure(
                code="html_dynamic_unreadable",
                message="此網站主要內容由 JavaScript 動態載入，無法穩定判讀。",
                hint="建議改用 RSS，或改成瀏覽器渲染模式（Playwright）後再監測。",
                retryable=False,
            )

    if not watch_description or not watch_description.strip():
        h = content_hash(full_text)
        source = "playwright_html" if playwright_used else "html"
        return full_text, h, {"status": "ok", "source": source, "confidence": 0.8, "hint": ""}

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
                source = "playwright_gemini" if playwright_used else "gemini"
                return extracted, h, {"status": "ok", "source": source, "confidence": 0.85, "hint": ""}
        except Exception:
            pass  # 失敗時 fallback 到全文

    # 無 AI 或失敗：回傳全文
    h = content_hash(full_text)
    source = "playwright_html_fallback" if playwright_used else "html_fallback"
    return full_text, h, {
        "status": "ok",
        "source": source,
        "confidence": 0.65,
        "hint": "AI 區塊擷取失敗，已改用整頁內容比對。",
    }
