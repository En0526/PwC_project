# RSS 功能使用指南

## 🎯 概述

新增的 RSS 功能套件提供了三項核心功能，幫助用戶快速發現、驗證和訂閱 RSS feed。

---

## ✨ 三大功能

### 1️⃣ **RSS 自動檢測** (Detect RSS Feeds)

從任何網站頁面自動發現 RSS/Atom feed 鏈接。

**如何使用：**
1. 在「RSS 功能」區塊的「檢測此頁面的 RSS feed」欄位輸入網址
   - 例如：`https://news.ycombinator.com`
2. 點擊「🔍 偵測 RSS」按鈕
3. 系統會：
   - 抓取頁面 HTML
   - 搜尋 `<link rel="alternate">` 標籤
   - 列出所有發現的 RSS/Atom feed

**結果顯示：**
```
✓ 找到 3 個 RSS feed

┌─ RSS Feed
│  https://example.com/feed.xml
│  [使用此 RSS]
│
├─ Atom Feed  
│  https://example.com/atom.xml
│  [使用此 RSS]
│
└─ (推測) RSS Feed (/feed)
   https://example.com/feed
   [使用此 RSS]
```

**點擊「使用此 RSS」後，該 URL 會自動填入新增訂閱表單，可直接點擊新增。**

---

### 2️⃣ **RSS 驗證** (Validate RSS Feed)

驗證指定的 URL 是否提供有效的 RSS/Atom feed。

**如何使用：**
1. 在「驗證 RSS feed 有效性」欄位輸入 RSS 源 URL
   - 例如：`https://feeds.bbc.co.uk/news/rss.xml`
2. 點擊「✓ 驗證」按鈕
3. 系統會：
   - 下載並解析 RSS/Atom 源
   - 檢查格式是否有效
   - 統計項目（item/entry）數量
   - 提取 Feed 標題

**成功結果示例：**
```
✓ 有效的 RSS feed，包含 35 項

標題：BBC News
類型：RSS
項目數：35
[使用此 RSS 網址]
```

**失敗結果示例：**
```
✗ 此 URL 不提供有效的 RSS/Atom feed
```

---

### 3️⃣ **RSS 源整合**

無論使用檢測或驗證功能，發現有效的 RSS 源後，都可以點擊「使用此 RSS」按鈕：
- URL 會自動填入「新增追蹤」表單
- Watch description 會被清空（RSS 通常監測整個 feed）
- 用戶可直接點擊「新增」按鈕完成訂閱

---

## 🔧 後端 API 端點

### POST /api/subscriptions/rss/detect

檢測網頁中的 RSS feed。

**請求：**
```json
{
  "url": "https://example.com"
}
```

**成功響應 (200)：**
```json
{
  "url": "https://example.com",
  "found": true,
  "message": "找到 3 個 RSS feed",
  "feeds": [
    {
      "url": "https://example.com/feed.xml",
      "title": "Latest Posts",
      "type": "rss",
      "is_guess": false
    },
    {
      "url": "https://example.com/atom.xml",
      "title": "Atom Feed",
      "type": "atom"
    }
  ]
}
```

**失敗響應 (400)：**
```json
{
  "url": "https://invalid-url.com",
  "found": false,
  "feeds": [],
  "message": "無法檢測 RSS：[錯誤原因]"
}
```

---

### POST /api/subscriptions/rss/validate

驗證 RSS feed 的有效性。

**請求：**
```json
{
  "url": "https://feeds.example.com/rss.xml"
}
```

**成功響應 (200)：**
```json
{
  "url": "https://feeds.example.com/rss.xml",
  "valid": true,
  "type": "rss",
  "items_count": 25,
  "title": "Example News Feed",
  "message": "✓ 有效的 RSS feed，包含 25 項"
}
```

**失敗響應 (400)：**
```json
{
  "url": "https://example.com/not-a-feed",
  "valid": false,
  "type": null,
  "items_count": 0,
  "title": "",
  "message": "✗ 此 URL 不提供有效的 RSS/Atom feed"
}
```

---

## 📦 實現細節

### 後端函數 (backend/services/scraper.py)

#### `detect_rss_feeds(html: str, base_url: str = "") -> list[dict]`

從 HTML 中檢測 RSS/Atom feed 鏈接。

- 搜尋 `<link rel="alternate">` 標籤
- 檢查 Content-Type 是否為 RSS/Atom
- 相對 URL 會轉為絕對 URL
- 返回 `[{"url": "...", "title": "...", "type": "rss|atom"}, ...]`

**支持的 RSS/Atom 類型：**
- `application/rss+xml` → `"rss"`
- `application/atom+xml` → `"atom"`
- `application/xml` (if contains `<rss>` or `<feed>`)
- `text/xml` (if contains `<rss>` or `<feed>`)

#### `validate_rss_feed(url: str, timeout: int = 10) -> dict`

驗證 URL 是否提供有效的 RSS/Atom feed。

**返回格式：**
```python
{
    "valid": bool,        # 是否為有效 RSS/Atom
    "type": str | None,   # "rss" 或 "atom" 或 None
    "items_count": int,   # 項目（item/entry）數量
    "title": str,         # Feed 標題
    "message": str        # 人類可讀的訊息
}
```

**驗證流程：**
1. Fetch URL
2. 檢查 Content-Type 或 HTML 前綴
3. 嘗試用 XML 解析
4. 判斷根元素是否為 `<rss>`, `<rdf>` 或 `<feed>`
5. 統計 `<item>` 或 `<entry>` 元素數量
6. 提取 `<title>` 作為 Feed 名稱

---

## 🌐 常見 RSS 源例子

### 新聞網站
- BBC News: `https://feeds.bbci.co.uk/news/rss.xml`
- Reuters: `https://feeds.reuters.com/reuters/businessNews`
- CNN: `http://rss.cnn.com/rss/edition.rss`

### 技術部落格
- Hacker News: `https://news.ycombinator.com/rss`
- GitHub Trending: `https://github.com/trending/python?spoken_language_code=zh&since=daily`
- Medium: `https://medium.com/feed/`

### 政府機構
- 台灣政府網站通常提供 RSS（需自行檢測）
- 例如：行政院、各部會通常有 `/News/RSS.aspx` 之類的路徑

---

## 🚀 使用場景

### 場景 1：快速訂閱新聞網站
1. 在「檢測此頁面的 RSS feed」輸入 `https://bbc.com`
2. 點擊「🔍 偵測 RSS」
3. 從結果中選擇官方 RSS（通常是最上面的）
4. 點擊「使用此 RSS」
5. 點擊「新增」即完成訂閱

### 場景 2：驗證 RSS URL 的有效性
1. 複製一個可能的 RSS 連結（例如 `/feed` 路徑）
2. 在「驗證 RSS feed 有效性」欄位貼上
3. 點擊「✓ 驗證」檢查是否有效
4. 如果有效，直接點擊「使用此 RSS 網址」

### 場景 3：處理重定向或複雜網站
- 有些網站的 RSS 鏈接在首頁不是直接可見的
- 使用「偵測 RSS」可以自動找到這些隱藏的 feed
- 即使只有推測結果（基於常見 URL 模式），也值得驗證一下

---

## 📋 故障排除

### Q: 偵測到的 RSS 都是「推測」狀態，能用嗎？
**A:** 推測的 RSS 源（標記為 `is_guess: true`）是基於常見 URL 模式（如 `/feed`, `/rss` 等）猜測的，不一定存在。建議：
1. 點擊「使用此 RSS」填入
2. 點擊「✓ 驗證」檢查是否有效
3. 如果驗證失敗，嘗試下一個推測源

### Q: 驗證說「不提供有效的 RSS」，怎麼辦？
**A:** 可能原因：
- URL 不是真實存在的 RSS 源（可能是 HTML 頁面）
- RSS 源需要身份驗證（此系統暫不支持）
- RSS 源格式不符合標準（可能是自訂 XML 格式）

**建議：**
1. 手動驗證 URL 是否能在瀏覽器中打開
2. 檢查網站是否確實有 RSS 功能（有些網站只有訂閱電子報）
3. 嘗試搜尋 `site:example.com RSS` 或 `site:example.com feed`

### Q: 為什麼偵測不到某些我知道存在的 RSS？
**A:** 原因可能：
- RSS 鏈接是通過 JavaScript 動態生成的（此系統只解析靜態 HTML）
- RSS 鏈接在頁面的其他位置（例如頁腳）
- RSS 使用不標準的 `<link>` 標籤屬性

**解決：** 使用「驗證 RSS」直接測試你知道的 RSS URL，或在網站的不同頁面（如首頁、關於頁面）使用「偵測」功能。

---

## 🔐 安全注意事項

- RSS 檢測和驗證只在後端進行，不暴露用戶信息
- 所有 HTTP 請求都有 10 秒超時限制，防止惡意 URL 導致伺服器卡頓
- 系統不保存 RSS 檢測的臨時結果，只返回給用戶

---

## 📊 統計與監控

- 每次檢測和驗證的 RSS 源都被系統記錄在日誌中
- 可用於後續分析：常見的 RSS 源、最受歡迎的網站等

---

## 🎓 進階用法

### 結合智能監測
使用 RSS 訂閱後，系統會：
1. 定期抓取 RSS feed
2. 將新項目與舊內容比對
3. 當發現新聞項時立即通知你

### 結合 AI 內容擷取
雖然 RSS 通常監測整個 feed，但你仍可在訂閱後編輯「要觀看的部分」欄位：
- 例如：「只關注標題包含『AI』的項目」
- AI 會幫你自動過濾相關內容

---

完整 RSS 功能已集成到系統中，祝監測愉快！ 🚀
