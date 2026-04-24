# 監測診斷指南 - 區分反爬 vs 沒有 RSS

## 新增診斷代碼

系統現在可以清晰地區分三大類故障：

### 1️⃣ **反爬阻擋** (Anti-Bot Blocking)
- `http_403` - 網站返回 403 禁止訪問
- `http_429` - 請求過於頻繁被限流
- `rss_fetch_failed_blocked` - RSS 源被反爬阻擋
- `rss_fetch_failed_timeout` - RSS 源超時

**用戶見到的提示：**
```
【反爬阻擋】RSS 源被網站拒絕
此 RSS 源被網站反爬阻擋（403/429），建議更換 feed 來源或稍後重試。
```

### 2️⃣ **無 RSS Feed** (Missing RSS)
- `rss_not_found` - URL 看起來像 RSS，但伺服器返回非 RSS 內容（HTML、錯誤頁等）
- `rss_parse_failed` - 返回了 XML，但格式不是有效的 RSS/Atom

**用戶見到的提示：**
```
【無 RSS Feed】此 URL 不提供 RSS
此連結不提供 RSS feed（可能是登入頁、錯誤頁等）。請改用其他 RSS 源，或改為監測網站的一般 HTML 頁面。
```

### 3️⃣ **動態頁面需要渲染** (Dynamic/JS-Heavy)
- `html_dynamic_unreadable` - HTML 內容主要由 JavaScript 動態載入

**用戶見到的提示：**
```
【動態頁面】需要 JavaScript 渲染
建議改用 RSS，或改成瀏覽器渲染模式（Playwright）後再監測。
```

---

## 前端展示

### 單次檢查 (checkOne)
當按下「立即檢查」按鈕時，失敗會顯示分類提示：

```
【反爬阻擋】RSS 源被網站拒絕
本次無法完成擷取（不會判定為「無更新」）。
詳情：此 RSS 源被網站反爬阻擋（403/429），建議更換 feed 來源或稍後重試。
提醒：此狀況通常重試也無效，建議改 RSS 或瀏覽器模式。
```

### 全部檢查 (checkAll)
當按下「全部檢查」時，會統計並按分類顯示失敗：

```
已完成全部手動檢查：5 個追蹤，發現 2 個更新。
其中 3 個無法判讀/擷取，不會算成「無更新」。
失敗分類：反爬（RSS） x2、無RSS x1
建議：【rss_fetch_failed_blocked】此 RSS 源被網站反爬阻擋（403/429），建議更換 feed 來源或稍後重試。
```

---

## 後端實現細節

### scraper.py
- **`_url_expects_rss(url)`**: 判斷 URL 是否看起來應該提供 RSS（包含 `/feed`, `/rss`, `/atom`, `.xml`）
- **`scrape_and_extract()`**: 
  1. 嘗試 fetch 網頁
  2. 如果 fetch 失敗且 URL 看起來像 RSS → 返回 `rss_fetch_failed*` 代碼
  3. 如果 fetch 成功但不是 RSS 格式且 URL 看起來像 RSS → 返回 `rss_not_found`
  4. 如果是 HTML 但需要 JS 渲染 → 返回 `html_dynamic_unreadable`

### scheduler.py
- **`run_check_subscription()`**: 捕捉 `ScrapeFailure` 並根據代碼生成中文提示信息
- 新增分類提示前綴：❌（無法取得）、⚠️（反爬/限流）、⏱️（超時/慢）

### dashboard.js
- **`checkOne()`**: 根據 `result_status` 判斷分類，顯示【分類】提示
- **`checkAll()`**: 統計失敗分類，按類別彙總

---

## 測試方式

### 測試反爬阻擋
```bash
# 添加一個看起來像 RSS 的 URL 並手動設置返回 403
# 預期見到：【反爬阻擋】RSS 源被網站拒絕
```

### 測試無 RSS Feed
```bash
# 添加一個看起來像 RSS（URL 含 /feed 等）但網站不提供的 URL
# 預期見到：【無 RSS Feed】此 URL 不提供 RSS
```

### 測試動態頁面
```bash
# 添加一個需要 JavaScript 渲染的網站（例如 React/Vue SPA）
# 預期見到：【動態頁面】需要 JavaScript 渲染
```

---

## API 響應格式

失敗時的 API 響應現在包含：
```json
{
  "ok": false,
  "error": "...",
  "result_status": "rss_fetch_failed_blocked",
  "hint": "此 RSS 源被網站反爬阻擋（403/429），建議更換 feed 來源或稍後重試。",
  "retryable": true,
  "http_status": 403,
  "source": "scraper"
}
```

關鍵字段：
- `result_status`: 診斷代碼，用於前端分類
- `hint`: 中文提示，向用戶解釋失敗原因和建議
- `retryable`: 是否應該提示用戶稍後重試
- `http_status`: HTTP 狀態碼（如果適用）
