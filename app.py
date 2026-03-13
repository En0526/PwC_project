"""
訂閱網站更新監測系統
- 使用者登入 → 新增追蹤網站與「要觀看的區塊」描述
- 定時檢查更新，有變更時通知並可比對差異
- 使用 Google AI Studio (Gemini) 解析使用者描述的觀看區塊
"""
import os
import sys

# 讓 D:\NTU_AI 成為專案根目錄
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import create_app
from backend.scheduler import init_scheduler

app = create_app()
init_scheduler(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
