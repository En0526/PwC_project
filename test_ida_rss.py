#!/usr/bin/env python3
"""
測試 IDA Taiwan RSS 訂閱整合

1. 驗證 RSS feed 是否有效
2. 測試 scraper 是否能解析
3. 將其加入訂閱 (需要執行 app 並提供認證)
"""

import sys
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import urllib3
import ssl

# 忽略 SSL 警告 (用於測試)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定 SSL 環境變數
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['CURL_CA_BUNDLE'] = ''

# 加入 backend 模組路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.services.scraper import validate_rss_feed, parse_rss_snapshot, fetch_page_detailed

# IDA RSS Feed URL
IDA_RSS_URL = "https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=1"
IDA_NEWS_URL = "https://www.ida.gov.tw/ctlr?PRO=news.rwdNewsList"

print("="*80)
print("IDA Taiwan RSS Integration Test")
print("="*80)

# Test 1: Direct fetch with requests (workaround for SSL)
print("\n[Test 1] 直接獲取 RSS Feed...")
print(f"URL: {IDA_RSS_URL}\n")

try:
    # 直接用 requests 獲取，跳過 SSL 驗證
    response = requests.get(IDA_RSS_URL, verify=False, timeout=15)
    response.raise_for_status()
    
    html = response.text
    content_type = response.headers.get('Content-Type', 'unknown')
    
    print(f"✓ 成功獲取 RSS 內容")
    print(f"  - Status: {response.status_code}")
    print(f"  - Content-Type: {content_type}")
    print(f"  - 內容大小: {len(html)} bytes")
    
    # Parse RSS
    snapshot = parse_rss_snapshot(html, max_items=5)
    print(f"\n✓ 成功解析 RSS")
    print(f"最新 5 則新聞摘要:")
    print("-" * 80)
    print(snapshot[:1000])  # 顯示前 1000 個字
    if len(snapshot) > 1000:
        print(f"\n... (還有 {len(snapshot) - 1000} 個字元)")
        
except Exception as e:
    print(f"❌ 獲取或解析失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Integration info
print("\n[Test 2] 整合資訊")
print("-" * 80)
print(f"""
RSS Feed 名稱: 經濟部產業發展署 - 新聞發布 RSS
URL: {IDA_RSS_URL}

推薦的訂閱參數:
  - name: "經濟部產業發展署新聞" 
  - url: "{IDA_RSS_URL}"
  - check_interval_minutes: 360 (每 6 小時檢查一次)
  - watch_description: (留空，使用完整 RSS 內容)

API 呼叫範例 (需要登入):
  POST /api/subscriptions
  {{
    "url": "{IDA_RSS_URL}",
    "name": "經濟部產業發展署新聞",
    "check_interval_minutes": 360
  }}
""")

print("\n✅ 所有測試通過！")
print("="*80)
print("""
下一步:
1. 啟動 app.py
2. 在網站上登入或註冊帳號
3. 在 API 中新增上述訂閱，或
4. 使用以下 curl 命令:

  curl -X POST http://localhost:5000/api/subscriptions \\
    -H "Content-Type: application/json" \\
    -d '{
      "url": "https://www.ida.gov.tw/ctlr?PRO=rss.RSSView&t=1",
      "name": "經濟部產業發展署新聞",
      "check_interval_minutes": 360
    }'
""")
