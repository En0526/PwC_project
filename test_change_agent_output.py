# -*- coding: utf-8 -*-
"""
驗證 change_agent 在 UTF-8 路徑下的實際輸出格式。
(避免 PowerShell heredoc 編碼問題)
"""
import sys
import io

# 強制 stdout 為 UTF-8（Windows 環境用）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from backend.services.change_agent import generate_change_report

previous_snapshot_text = """[站點] 經濟部
[區塊] 新聞與公告 > 本部新聞
[來源] https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=1&menu_id=40
[總筆數] 619
[新聞列表]
  [2026-04-27] 春雨改善各地水情 新竹水情燈號轉為綠燈（水利署 19:05） | https://www.moea.gov.tw/MNS/populace/news/News_Content.aspx?n=A02&sms=4&s=100001
  [2026-04-27] 經濟部成立量子產業技術推動辦公室（產業技術司 14:15） | https://www.moea.gov.tw/MNS/populace/news/News_Content.aspx?n=A02&sms=4&s=100002
  [2026-04-25] 第二屆智慧創新大賞百大贏家出爐（產業技術司 18:00） | https://www.moea.gov.tw/MNS/populace/news/News_Content.aspx?n=A02&sms=4&s=100003"""

current_snapshot_text = """[站點] 經濟部
[區塊] 新聞與公告 > 本部新聞
[來源] https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=1&menu_id=40
[總筆數] 621
[新聞列表]
  [2026-04-28] 公告修正工廠管理輔導法施行細則第五條附表（法制處 10:00） | https://www.moea.gov.tw/MNS/populace/news/News_Content.aspx?n=A02&sms=4&s=100005
  [2026-04-28] 第七屆總統創新獎揭曉 跨域創新成國家韌性關鍵（產業技術司 15:00） | https://www.moea.gov.tw/MNS/populace/news/News_Content.aspx?n=A02&sms=4&s=100004
  [2026-04-27] 春雨改善各地水情 新竹水情燈號轉為綠燈（水利署 19:05） | https://www.moea.gov.tw/MNS/populace/news/News_Content.aspx?n=A02&sms=4&s=100001
  [2026-04-27] 經濟部成立量子產業技術推動辦公室（產業技術司 14:15） | https://www.moea.gov.tw/MNS/populace/news/News_Content.aspx?n=A02&sms=4&s=100002
  [2026-04-25] 第二屆智慧創新大賞百大贏家出爐（產業技術司 18:00） | https://www.moea.gov.tw/MNS/populace/news/News_Content.aspx?n=A02&sms=4&s=100003"""

watch_description = "只監測「首頁 > 新聞與公告 > 本部新聞」列表。Agent 2 僅整理新增或移除中與法規、公告、政策發布、公告送達相關的項目，忽略一般宣傳性新聞。"

report = generate_change_report(
    url="https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=1&menu_id=40",
    site_name="經濟部",
    previous_snapshot=previous_snapshot_text,
    current_snapshot=current_snapshot_text,
    watch_description=watch_description,
)

print("=" * 50)
print("【Agent 2 輸出結果】")
print("=" * 50)
print(report)
print("=" * 50)

# 也驗證 focus keywords 提取
from backend.services.change_agent import _extract_focus_keywords
keywords = _extract_focus_keywords(watch_description)
print(f"\n【提取到的關注關鍵詞】: {keywords}")
