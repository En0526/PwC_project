# 經濟部產業發展署 (IDA) RSS 完整指南

## 🎯 主要整合

✅ **已整合到平台**: **新聞發布 RSS**

```
名稱: 經濟部產業發展署新聞
URL:  https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=1
狀態: ✅ 已驗證，已文檔化
更新頻率: 每週 2-5 則新聞
```

---

## 📰 完整 RSS 訊息源列表

IDA 官方提供 8 種 RSS feeds，適用於不同用途:

### 1. 📌 新聞發布 RSS (已整合)
```
URL: https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=1
內容: 產業政策新聞、重大宣布、成果報告
更新: 定期 (2-5 則/週)
推薦檢查頻率: 360 分鐘 (6 小時)
```
**典型內容**: AI 政策、投資優惠措施、產業發展成果

---

### 2. 🏭 業務活動訊息 RSS
```
URL: https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=10
內容: 活動、座談會、展覽、研討會
更新: 活動期間頻繁
推薦檢查頻率: 1440 分鐘 (每天)
```
**典型內容**: 產業輔導活動、業者交流活動、專業研討會

---

### 3. ⚖️ 產業發展法令規章 RSS
```
URL: https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=2
內容: 新法令、修正案、規範公告
更新: 定期 (法令異動)
推薦檢查頻率: 1440 分鐘 (每天)
```
**典型內容**: 產業創新條例、投資優惠法規、補助辦法

---

### 4. 📢 招標公告 RSS
```
URL: https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=3
內容: 政府採購、業界招募、合作案招標
更新: 根據招標進度
推薦檢查頻率: 1440 分鐘 (每天)
```
**典型內容**: 委託服務、軟體開發、研究計畫

---

### 5. 📚 政府出版品 RSS
```
URL: https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=4
內容: 白皮書、統計報告、研究出版品
更新: 定期 (月度/季度)
推薦檢查頻率: 2880 分鐘 (2 天)
```
**典型內容**: 產業白皮書、市場分析報告、統計資料

---

### 6. 🔍 政府資訊公開 RSS
```
URL: https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=6
內容: 政府資訊公開、FOIA 文件
更新: 定期
推薦檢查頻率: 10080 分鐘 (每週)
```
**典型內容**: 預算公開、決算公開、會議紀錄

---

### 7. ❓ 業者常見問答 RSS
```
URL: https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=7
內容: FAQ 更新、常見問題解答
更新: 根據業者詢問
推薦檢查頻率: 10080 分鐘 (每週)
```
**典型內容**: 申請程序、補助資格、行政規定

---

### 8. 🎯 施政措施 RSS
```
URL: https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=8
內容: 部長施政報告、政策宣示、重大措施
更新: 定期
推薦檢查頻率: 1440 分鐘 (每天)
```
**典型內容**: 施政重點、政策方向、關鍵計畫

---

## 🚀 如何新增其他 RSS Feeds

### 方式 1: 通過 Web 界面
1. 進入儀表板
2. 點擊 "+ 新增追蹤網站"
3. 複製上面的 RSS URL
4. 填入名稱和檢查頻率

### 方式 2: API 調用
```bash
# 招標公告
curl -X POST http://localhost:5000/api/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=3",
    "name": "IDA 招標公告",
    "check_interval_minutes": 1440
  }'

# 法令規章
curl -X POST http://localhost:5000/api/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=2",
    "name": "IDA 法令規章",
    "check_interval_minutes": 1440
  }'

# 業務活動
curl -X POST http://localhost:5000/api/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=10",
    "name": "IDA 業務活動",
    "check_interval_minutes": 1440
  }'
```

---

## 📋 建議的監控組合

### 方案 A: 政策決策者
```
✓ 新聞發布 (360 min - 6小時)
✓ 施政措施 (1440 min - 每天)
✓ 產業發展法令規章 (1440 min - 每天)
```
**目的**: 快速掌握政策動向

---

### 方案 B: 業界參與者
```
✓ 新聞發布 (360 min - 6小時)
✓ 招標公告 (1440 min - 每天)
✓ 業務活動訊息 (1440 min - 每天)
✓ 常見問答 (10080 min - 每週)
```
**目的**: 把握商機，掌握活動

---

### 方案 C: 研究機構
```
✓ 新聞發布 (1440 min - 每天)
✓ 政府出版品 (2880 min - 每 2 天)
✓ 政府資訊公開 (10080 min - 每週)
✓ 法令規章 (1440 min - 每天)
```
**目的**: 收集數據和報告

---

### 方案 D: 完整監控 (超級用戶)
```
✓ 所有 8 個 RSS feeds
✓ 檢查頻率依重要性調整
✓ 使用自訂通知規則
```
**目的**: 完整掌握 IDA 動態

---

## 💾 批量導入設定

如果要一次新增多個 RSS feeds，可使用此 Python 腳本:

```python
#!/usr/bin/env python3
"""批量新增 IDA RSS 訂閱"""

from backend import create_app
from backend.models import db, Subscription

app = create_app()

IDA_FEEDS = [
    {"t": 1, "name": "新聞發布", "interval": 360},
    {"t": 2, "name": "法令規章", "interval": 1440},
    {"t": 3, "name": "招標公告", "interval": 1440},
    {"t": 4, "name": "政府出版品", "interval": 2880},
    {"t": 6, "name": "政府資訊公開", "interval": 10080},
    {"t": 7, "name": "常見問答", "interval": 10080},
    {"t": 8, "name": "施政措施", "interval": 1440},
    {"t": 10, "name": "業務活動", "interval": 1440},
]

with app.app_context():
    user_id = 1  # 調整為目標用戶 ID
    
    for feed in IDA_FEEDS:
        url = f"https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t={feed['t']}"
        name = f"IDA - {feed['name']} RSS"
        
        sub = Subscription(
            user_id=user_id,
            url=url,
            name=name,
            check_interval_minutes=feed['interval']
        )
        db.session.add(sub)
    
    db.session.commit()
    print("✓ 所有 IDA RSS feeds 已新增")
```

---

## 📊 典型工作流程

```
早上 08:00 - 檢查「施政措施」和「新聞發布」
     ↓
午間 12:00 - 檢查「招標公告」是否有新機會
     ↓
下午 15:00 - 查閱「業務活動」了解即將舉辦的活動
     ↓
週末 - 詳讀「政府出版品」和「政府資訊公開」
     ↓
隨時 - 收到通知時立即查看关鍵新聞
```

---

## 🔗 相關資源

- **IDA 官網**: https://www.ida.gov.tw/
- **RSS 說明頁**: https://www.ida.gov.tw/ctlr?PRO=rss.RSSList&lang=0
- **新聞首頁**: https://www.ida.gov.tw/ctlr?PRO=news.NewsList&lang=0
- **聯絡方式**: 各 RSS 頁面都有聯絡資訊

---

## ⚙️ 客製化提示

### 特定產業監控

如果只想監控特定產業，可在 `watch_description` 設定:

```
"只監控電子資訊產業和 AI 相關的新聞"
"關注半導體、晶片、軟體的政策"
"追蹤永續發展和環保相關新聞"
```

系統會使用 AI 提取相關內容後進行比對。

### 緊急政策通知

若要即時獲得最新政策：
```
check_interval_minutes: 60  # 每小時檢查
enable_email_notifications: true  # 啟用郵件
watch_description: "任何新的政策公告"
```

---

## ✨ 集成優勢

✅ **統一界面** - 所有 RSS 在同一平台查看  
✅ **差異追蹤** - 自動檢測更新，顯示差異  
✅ **多渠道通知** - 應用內 + 郵件通知  
✅ **靈活設定** - 調整檢查頻率，無需代碼修改  
✅ **完整歷史** - 保留所有快照，支援回溯  

---

**文檔建立日期**: 2026-04-28  
**IDA RSS 整合狀態**: ✅ 完全就緒

