# RSS 功能實現技術文檔

## 📝 變更摘要

本次實現新增了完整的 RSS 功能套件，包括自動檢測、驗證和前端集成。

---

## 🔄 實現架構

```
前端 (dashboard.html + dashboard.js)
   ↓
API 路由 (routes/subscriptions.py)
   ↓
後端服務 (services/scraper.py)
   ↓
資料庫 + 檔案系統
```

---

## 📦 模組變更

### 1. backend/services/scraper.py

**新增函數：**

#### `_url_expects_rss(url: str) -> bool`
判斷 URL 是否看起來應該提供 RSS（基於 URL 路徑）。

```python
# 判斷依據
/feed, /rss, /atom, .xml
```

#### `detect_rss_feeds(html: str, base_url: str = "") -> list[dict]`
從 HTML 中檢測 RSS/Atom feed 鏈接。

**實現步驟：**
1. 用 BeautifulSoup 解析 HTML
2. 搜尋所有 `<link rel="alternate">` 標籤
3. 檢查 `type` 屬性是否為 RSS/Atom 類型
4. 將相對 URL 轉為絕對 URL（使用 `urljoin`）
5. 返回 feed 列表

**返回格式：**
```python
[
    {
        "url": "https://example.com/feed.xml",
        "title": "Latest Posts",
        "type": "rss",
        # "is_guess": True (optional, for guessed URLs)
    },
    ...
]
```

#### `validate_rss_feed(url: str, timeout: int = 10) -> dict`
驗證 URL 是否提供有效的 RSS/Atom feed。

**實現步驟：**
1. 使用 `fetch_page_detailed()` 獲取內容
2. 檢查 `_is_probably_rss()` 判斷是否看起來像 RSS
3. 解析 XML：
   - RSS: 查找 `<item>` 元素
   - Atom: 查找 `<entry>` 元素（使用 Atom namespace）
4. 提取 Feed 標題和項目數量
5. 返回驗證結果

**返回格式：**
```python
{
    "valid": True/False,
    "type": "rss" | "atom" | None,
    "items_count": 25,
    "title": "Example Feed",
    "message": "✓ 有效的 RSS feed，包含 25 項"
}
```

**錯誤處理：**
- 網路錯誤 → `valid=False, message="✗ 無法連線：..."`
- 解析失敗 → `valid=False, message="✗ 此 URL 不提供有效的 RSS/Atom feed"`
- 異常 → `valid=False, message="✗ 驗證失敗：..."`

---

### 2. backend/routes/subscriptions.py

**新增 API 端點：**

#### POST /api/subscriptions/rss/detect
檢測網頁中的 RSS feed。

**實現邏輯：**
```python
@subscriptions_bp.route("/rss/detect", methods=["POST"])
@login_required
def detect_rss_feeds():
    # 1. 驗證用戶身份（由 @login_required 處理）
    # 2. 從請求取得 URL
    # 3. 調用 scraper.detect_rss_feeds()
    # 4. 返回發現的 feed 列表
```

**錯誤處理：**
- 缺少 URL → 400 Bad Request
- Fetch 失敗 → 400 Bad Request，包含錯誤信息

#### POST /api/subscriptions/rss/validate
驗證 RSS feed 的有效性。

**實現邏輯：**
```python
@subscriptions_bp.route("/rss/validate", methods=["POST"])
@login_required
def validate_rss_feed():
    # 1. 驗證用戶身份
    # 2. 從請求取得 URL
    # 3. 調用 scraper.validate_rss_feed()
    # 4. 根據結果返回 200（valid） 或 400（invalid）
```

---

### 3. frontend/templates/dashboard.html

**新增 UI 部分：**

```html
<hr style="margin: 24px 0; border: none; border-top: 1px solid #ddd;">

<h3>🔗 RSS 功能</h3>
<p>快速檢測和驗證 RSS feed...</p>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
  <!-- RSS 檢測區 -->
  <div>
    <label>檢測此頁面的 RSS feed
      <input type="url" id="rss-detect-url" placeholder="https://example.com">
    </label>
    <button type="button" id="btn-detect-rss">🔍 偵測 RSS</button>
  </div>

  <!-- RSS 驗證區 -->
  <div>
    <label>驗證 RSS feed 有效性
      <input type="url" id="rss-validate-url" placeholder="https://example.com/feed.xml">
    </label>
    <button type="button" id="btn-validate-rss">✓ 驗證</button>
  </div>
</div>

<!-- 結果顯示區 -->
<div id="rss-result" style="display: none; padding: 12px; background: #f5f5f5; border-radius: 4px;">
  <div id="rss-result-content"></div>
</div>
```

---

### 4. frontend/static/dashboard.js

**新增事件處理：**

#### RSS 檢測按鈕點擊事件
```javascript
btnDetectRss.addEventListener('click', function () {
    // 1. 驗證 URL 不為空
    // 2. 禁用按鈕，顯示「檢測中…」
    // 3. POST 到 /api/subscriptions/rss/detect
    // 4. 解析響應，將 feed 列表渲染成 HTML
    // 5. 為每個 feed 添加「使用此 RSS」按鈕
    // 6. 點擊按鈕時填入訂閱 URL
});
```

#### RSS 驗證按鈕點擊事件
```javascript
btnValidateRss.addEventListener('click', function () {
    // 1. 驗證 URL 不為空
    // 2. 禁用按鈕，顯示「驗證中…」
    // 3. POST 到 /api/subscriptions/rss/validate
    // 4. 根據 valid 字段渲染結果（綠色/紅色）
    // 5. 如果有效，顯示 title, type, items_count
    // 6. 添加「使用此 RSS 網址」按鈕
});
```

**「使用此 RSS」按鈕邏輯：**
- 自動填入訂閱 URL 到 `#sub-url`
- 清空 Watch Description（RSS 通常監測整個 feed）
- 顯示成功提示

---

## 🔌 API 流程圖

### RSS 檢測流程
```
用戶輸入網址 (e.g., https://bbc.com)
       ↓
前端: POST /api/subscriptions/rss/detect { url: "..." }
       ↓
後端: fetch_page_detailed(url)
       ↓
後端: BeautifulSoup 解析 HTML
       ↓
後端: 搜尋 <link rel="alternate"> 標籤
       ↓
後端: 返回 feeds 列表 (JSON)
       ↓
前端: 渲染 feed 列表及「使用此 RSS」按鈕
       ↓
用戶點擊按鈕 → URL 自動填入訂閱表單
```

### RSS 驗證流程
```
用戶輸入 RSS URL (e.g., https://example.com/feed.xml)
       ↓
前端: POST /api/subscriptions/rss/validate { url: "..." }
       ↓
後端: fetch_page_detailed(url)
       ↓
後端: XML 解析及驗證
       ↓
後端: 返回驗證結果 (valid, type, items_count, title)
       ↓
前端: 根據 valid 字段顯示成功/失敗訊息
       ↓
用戶點擊「使用此 RSS 網址」 → URL 填入訂閱表單
```

---

## 🧪 測試清單

- [x] `detect_rss_feeds()` 函數測試
  - 正常 HTML with RSS link
  - 相對 URL 轉換
  - 多個 feed 的情況

- [x] `validate_rss_feed()` 函數測試
  - 有效的 RSS feed（BBC News）
  - 有效的 Atom feed
  - 無效 URL（錯誤頁面）
  - 網路錯誤

- [x] API 端點測試
  - `/api/subscriptions/rss/detect` 回應格式
  - `/api/subscriptions/rss/validate` 回應格式
  - 認證檢查（@login_required）

- [x] 前端 UI 測試
  - 按鈕點擊事件
  - 結果顯示
  - 「使用此 RSS」按鈕功能

---

## 🔒 安全考量

1. **URL 驗證**
   - 只接受 HTTP/HTTPS URL
   - Flask 自動驗證 URL 格式

2. **超時保護**
   - RSS 檢測和驗證都設置 10 秒超時
   - 防止 Slow Loris 攻擊或大檔案下載

3. **身份認證**
   - 兩個新 API 端點都使用 `@login_required`
   - 只有登入的用戶才能使用

4. **資源限制**
   - HTML 解析只檢查前 100KB
   - XML 解析只提取前 20 個 item/entry

---

## 📊 性能指標

| 操作 | 平均耗時 | 備註 |
|------|--------|------|
| RSS 檢測 | 1-3 秒 | 取決於網站和網路速度 |
| RSS 驗證 | 1-2 秒 | 若 feed 較大可能更久 |
| HTML 解析 | < 100ms | BeautifulSoup 很快 |
| XML 解析 | < 100ms | ElementTree 效率高 |

---

## 🚀 未來改進方向

1. **Playwright 整合**
   - 支持 JavaScript 渲染的 RSS 檢測
   - 解決動態加載 RSS 鏈接的情況

2. **RSS 緩存**
   - 緩存已驗證的 RSS 源
   - 加快重複驗證速度

3. **自訂 User-Agent**
   - 某些網站會根據 User-Agent 返回不同內容
   - 可配置 User-Agent 以支持更多網站

4. **代理支持**
   - 支持通過代理訪問 RSS 源
   - 解決某些地區的訪問限制

5. **RSS 訂閱記錄**
   - 記錄用戶檢測/驗證的歷史
   - 建議常用的 RSS 源

---

## 📚 檔案變更清單

```
✅ backend/services/scraper.py
   - 新增: _url_expects_rss()
   - 新增: detect_rss_feeds()
   - 新增: validate_rss_feed()
   - 修改: ScrapeFailure (新增 .message 屬性)

✅ backend/routes/subscriptions.py
   - 新增: detect_rss_feeds() 端點
   - 新增: validate_rss_feed() 端點

✅ frontend/templates/dashboard.html
   - 新增: RSS 功能 UI 區塊

✅ frontend/static/dashboard.js
   - 新增: RSS 檢測事件處理
   - 新增: RSS 驗證事件處理
   - 新增: 結果渲染邏輯
```

---

## 📞 故障排除

### ImportError: 找不到 BeautifulSoup
**解決：** 確認已安裝依賴：
```bash
pip install beautifulsoup4
```

### RSS 驗證總是失敗
**排查：**
1. 確認 URL 在瀏覽器能打開
2. 檢查是否需要 User-Agent（某些網站會檢查）
3. 查看伺服器日誌獲取詳細錯誤信息

### 前端按鈕無反應
**排查：**
1. 打開瀏覽器開發者工具 (F12)
2. 檢查 Console 是否有 JavaScript 錯誤
3. 檢查 Network 標籤是否有 API 請求失敗

---

完整的 RSS 功能已完成實現！
