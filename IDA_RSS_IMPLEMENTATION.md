# IDA Taiwan RSS 整合 - 完整實施方案

## 📊 執行摘要

✅ **經濟部產業發展署 (IDA Taiwan) 新聞 RSS 已成功整合到平台**

| 檢查項目 | 狀態 | 備註 |
|---------|------|------|
| RSS Feed 可用性 | ✅ 有效 | 36KB 內容，應用/rss+xml |
| 平台兼容性 | ✅ 支援 | scraper 可完整解析 |
| 自動更新檢查 | ✅ 就位 | 後台調度程式已就位 |
| 差異比對系統 | ✅ 就位 | diff_match_patch 已配置 |
| 通知系統 | ✅ 就位 | 應用內 + 郵件通知 |

---

## 🎯 RSS Feed 詳情

```
名稱: 經濟部產業發展署 - 新聞發布 RSS
URL:  https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=1
類型: RSS 2.0
內容類型: application/rss+xml;charset=utf-8
內容大小: ~36 KB
更新頻率: 隨時 (通常每週 2-5 則新聞)
```

### 覆蓋的產業類別

- 知識經濟產業 (AI、軟體、晶片)
- 電子資訊產業
- 民生化工產業
- 金屬機電產業
- 永續發展

---

## 🚀 快速開始

### 1️⃣ 自動設定 (推薦)

```bash
# 進入專案目錄
cd c:\Users\lulu1\PwC_project

# 執行設定腳本 (自動建立測試用戶和訂閱)
python setup_ida_subscription.py

# 啟動應用
python app.py
```

**登入資訊** (由 setup 腳本建立):
- 帳號: `ida_tracker@example.com`
- 密碼: `ida_tracking_2026`

### 2️⃣ 手動設定

1. 啟動應用: `python app.py`
2. 在 http://localhost:5000 註冊帳號
3. 進入儀表板，點擊 "+ 新增追蹤網站"
4. 填入以下資訊:
   - **URL**: `https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=1`
   - **名稱**: `經濟部產業發展署新聞`
   - **檢查頻率**: `360 分鐘 (6 小時)`
   - **監看區塊**: (空白)

### 3️⃣ API 方式

```bash
curl -X POST http://localhost:5000/api/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=1",
    "name": "經濟部產業發展署新聞",
    "check_interval_minutes": 360
  }'
```

---

## 📋 平台如何處理 RSS 更新

### 1. 自動檢查週期
- 每 6 小時檢查一次 RSS feed
- 時間可在訂閱設定中調整 (1分鐘 到 1年)
- 後台調度程式自動運行，無需手動干預

### 2. 變更偵測
```
步驟 1: 獲取 RSS 內容
         ↓
步驟 2: 計算 SHA-256 hash
         ↓
步驟 3: 與上次儲存的 hash 比較
         ↓
步驟 4: 如果相同 → 無更新
         如果不同 → 進行詳細比對
         ↓
步驟 5: 生成差異摘要 (新增/移除的項目)
         ↓
步驟 6: 建立通知 + 發送郵件 (如已配置)
```

### 3. 通知內容

**應用內通知示例:**
```
[新聞發布] 有更新
2026-04-28 14:30

新增:
+ 為產業請命 經濟部呼籲維持現行空污法制度 避免衝擊國內8千家業者生計及供電
+ 以 AI 感測晶片與抗噪技術，為智慧座艙注入靈魂

[查看完整差異]
```

**電郵通知範本:**
- 訂閱名稱
- 更新時間
- 新增/移除項目清單 (前 6 項)
- 完整內容連結

---

## 🔧 技術架構

### 後端數據流

```
┌─────────────────────────────────────────────────────────┐
│                   定期調度器 (Scheduler)                  │
│            每 6 小時執行一次 check_subscription()          │
└────────────────────────────┬────────────────────────────┘
                             │
                    ↓ 獲取訂閱列表
                             │
┌────────────────────────────────────────────────────────┐
│                      Scraper 服務                       │
│  - 檢測 RSS feed (detect_rss_feeds)                    │
│  - 驗證 RSS 有效性 (validate_rss_feed)                 │
│  - 解析 RSS 內容 (parse_rss_snapshot)                  │
└──────────────────────┬─────────────────────────────────┘
                       │
                ↓ 擷取快照文字
                       │
┌────────────────────────────────────────────────────────┐
│                    差異比對服務                          │
│           - 計算 hash                                   │
│           - 比較新舊版本                                │
│           - 生成 diff 摘要                              │
└──────────────────────┬─────────────────────────────────┘
                       │
                ↓ 有變更?
                       │
             是 → 建立通知
                  發送郵件
                  更新 last_changed_at
                       │
┌────────────────────────────────────────────────────────┐
│                     資料庫儲存                          │
│  - Subscription (訂閱記錄)                             │
│  - Snapshot (內容快照 - 每次檢查儲存)                  │
│  - Notification (用戶通知)                            │
└────────────────────────────────────────────────────────┘
```

### 核心元件

| 元件 | 位置 | 功能 |
|------|------|------|
| **Scheduler** | `backend/scheduler.py` | 後台定時檢查 |
| **Scraper** | `backend/services/scraper.py` | RSS 解析和內容擷取 |
| **Diff Service** | `backend/services/diff_service.py` | 差異比對和摘要生成 |
| **Email Service** | `backend/services/email_service.py` | 郵件通知 (可選) |
| **Subscriptions Route** | `backend/routes/subscriptions.py` | API 端點 |
| **Models** | `backend/models/__init__.py` | 資料庫模型 |

---

## 📁 新增的文件

### 已建立

1. **IDA_RSS_INTEGRATION_GUIDE.md**
   - 詳細的用戶指南
   - 訂閱步驟
   - 故障排除

2. **test_ida_rss.py**
   - RSS feed 驗證測試
   - 內容解析測試
   - SSL 處理

3. **setup_ida_subscription.py**
   - 自動化設定腳本
   - 測試用戶建立
   - 訂閱初始化

---

## ⚙️ 郵件通知配置 (可選)

若要啟用郵件通知，編輯 `backend/config.py`:

```python
# 郵件設定範例 (Gmail)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_FROM = "your_email@gmail.com"
SMTP_USERNAME = "your_email@gmail.com"
SMTP_PASSWORD = "your_app_password"  # 使用應用密碼，不是帳戶密碼
SMTP_USE_TLS = True
```

**配置後:**
- 每次 RSS 更新時自動發送郵件
- 郵件包含差異摘要和直接連結

---

## 🧪 測試命令

### 列出訂閱
```bash
curl http://localhost:5000/api/subscriptions \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 手動觸發檢查
```bash
curl -X POST http://localhost:5000/api/subscriptions/{id}/check \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 查詢訂閱詳情
```bash
curl http://localhost:5000/api/subscriptions/{id} \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 查詢通知
```bash
curl http://localhost:5000/api/notifications \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🐛 常見問題

**Q: RSS feed 為什麼沒有更新?**
A: 檢查:
1. 平台是否在運行並且 scheduler 已啟動
2. 檢查頻率設定 (預設 6 小時)
3. 手動觸發檢查: `/api/subscriptions/{id}/check`
4. 查看應用日誌是否有錯誤

**Q: 如何加快更新頻率?**
A: 在訂閱設定中將 `check_interval_minutes` 改為較小值，例如:
- 60: 每小時
- 30: 每 30 分鐘
- 1: 每分鐘

**Q: 可以只監控特定內容嗎?**
A: 可以！設定 `watch_description` 為:
```
只監控「知識經濟產業」和「AI」相關的新聞
```
系統將使用 AI 提取相關內容後進行比對

---

## 📊 預期結果

### 第一次檢查後
- ✅ 訂閱創建成功
- ✅ 初始快照已儲存
- ✅ `last_checked_at` 更新為檢查時間

### 後續檢查 (當 RSS 有新聞時)
- ✅ 偵測到變更
- ✅ 差異摘要生成
- ✅ 通知建立
- ✅ 郵件發送 (若已配置)
- ✅ `last_changed_at` 更新

---

## 🎓 學習資源

- **RSS 格式**: 
  - https://www.ida.gov.tw/ctlr?PRO=rss.RSSList&lang=0 (官方說明)
  
- **其他可用的 IDA RSS**:
  - 業務活動訊息: `t=10`
  - 法令規章: `t=2`
  - 招標公告: `t=3`
  - 政府出版品: `t=4`
  - 政府資訊公開: `t=6`
  - 業者常見問答: `t=7`
  - 施政措施: `t=8`

---

## ✨ 特色功能

✅ **完整 RSS 支援** - 自動偵測和驗證 RSS/Atom feeds  
✅ **智慧差異比對** - 使用 diff_match_patch 生成人可讀的摘要  
✅ **雙通知** - 應用內 + 郵件通知  
✅ **靈活檢查頻率** - 1 分鐘到 1 年自訂  
✅ **內容快照** - 完整歷史記錄，支援回溯查詢  
✅ **AI 內容擷取** - 使用 Gemini AI 提取特定區塊  

---

## 📝 檢查清單

設定完成後驗證:

- [ ] 應用已啟動 (python app.py)
- [ ] 用戶帳號已建立
- [ ] IDA RSS 訂閱已新增
- [ ] Scheduler 正在運行 (查看日誌)
- [ ] 手動檢查成功執行
- [ ] 有新聞時收到通知
- [ ] 差異摘要正確顯示
- [ ] 郵件通知正常 (若已配置)

---

**整合完成日期**: 2026-04-28  
**平台版本**: 支援 RSS/Atom  
**狀態**: ✅ 生產就緒

