# 訂閱網站更新監測系統

使用者登入後可新增「追蹤網站」，並描述**要觀看是否有更新的部分**（例如：公告列表、最新消息區塊）。系統會定時擷取該區塊內容，有變更時可查看差異；並可選用 **Google AI Studio (Gemini)** 依你的描述從網頁中擷取對應區塊。

## 功能

- **登入 / 註冊**：使用信箱與密碼
- **新增追蹤**：輸入網址、自訂名稱、選填「要觀看的區塊」描述
- **定時檢查**：背景每 N 分鐘檢查一次所有訂閱（可在 `.env` 設定）
- **立即檢查**：手動觸發單一訂閱的檢查
- **差異比對**：有變更時可點「看差異」查看前後內容差異摘要
- **Google AI Studio**：若有設定 `GEMINI_API_KEY`，會用 Gemini 依你的描述從網頁擷取關注區塊，提高比對精準度

## 環境需求

- Python 3.10+
- （選用）Google AI Studio API Key：用於依描述擷取網頁區塊

## 安裝與執行

```bash
cd D:\NTU_AI
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

複製環境變數範例並編輯：

```bash
copy .env.example .env
```

在 `.env` 中設定：

- `FLASK_SECRET_KEY`：任意隨機字串（生產環境必填）
- `GEMINI_API_KEY`：（選填）在 [Google AI Studio](https://aistudio.google.com/apikey) 取得
- `CHECK_INTERVAL_MINUTES`：（選填）排程檢查間隔（系統全域定時觸發），預設 30 分鐘；如要立即就能用訂閱自訂「每分鐘」，可設定為 1 分鐘。

新增訂閱時可指定：
- 每分鐘（開發用）
- 每天
- 每周
- 每季
- 每半年
- 每年

建立資料庫並啟動：

```bash
python app.py
```

瀏覽器開啟：<http://127.0.0.1:5000>  
未登入會導向登入頁，註冊後即可在「我的追蹤網站」新增網址與觀看描述。

## 專案結構

```
D:\NTU_AI\
├── app.py                 # 程式進入點
├── requirements.txt
├── .env.example
├── backend/
│   ├── config.py          # 設定
│   ├── __init__.py        # Flask app 建立、登入管理
│   ├── scheduler.py       # 定時檢查訂閱
│   ├── models/            # User, Subscription, Snapshot
│   ├── routes/            # auth, subscriptions, pages
│   └── services/
│       ├── scraper.py     # 抓取網頁、擷取關注區塊
│       ├── gemini_service.py  # 使用 Gemini 解析觀看區塊
│       └── diff_service.py     # 文字差異比對
└── frontend/
    ├── templates/         # 登入、註冊、儀表板
    └── static/            # style.css, dashboard.js
```

## 與同學共編（Git + GitHub）

用 **Git + GitHub** 把專案放到雲端，兩人可各自 clone、改完再 push，是最常見的共編方式。

### 你（專案擁有者）第一次設定

1. **在專案目錄初始化 Git 並提交**
   ```bash
   cd D:\NTU_AI
   git init
   git add .
   git commit -m "Initial: 訂閱網站更新監測系統"
   ```

2. **在 GitHub 建立新倉庫**
   - 登入 [GitHub](https://github.com) → 點右上角 **+** → **New repository**
   - 名稱可填 `NTU_AI` 或自訂，**不要**勾選 "Add a README"（本地已有）
   - 建立後記下倉庫網址，例如：`https://github.com/En0526/PwC_project.git`

3. **把本地專案推上去**
   ```bash
   git remote add origin https://github.com/En0526/PwC_project.git
   git branch -M main
   git push -u origin main
   ```

4. **加同學為共同開發者**
   - 進該倉庫 → **Settings** → **Collaborators** → **Add people**
   - 輸入同學的 GitHub 帳號，送出邀請；同學接受後即可 push。

### 同學第一次參與（協作者要怎麼用）

**前提**：專案擁有者（En0526）已經在 GitHub 倉庫的 **Settings → Collaborators** 加你為共同開發者，並且你已在 GitHub 接受邀請。

1. **安裝 Git**（若尚未安裝）：[git-scm.com](https://git-scm.com/)  
   安裝 Python 3.10+（若尚未安裝）：[python.org](https://www.python.org/)

2. **複製專案到本機**（請用實際倉庫名稱，目前為 `PwC_project`）
   ```bash
   git clone https://github.com/En0526/PwC_project.git
   cd PwC_project
   ```

3. **建環境、裝套件、設定**
   - **Windows（PowerShell）**：在專案目錄執行  
     `.\setup_env.ps1`  
     若沒有該腳本，就手動執行：
     ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```
   - **Mac / Linux**：
     ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```
   - 編輯 `.env`，至少設定 `FLASK_SECRET_KEY`（任意隨機字串）。

4. **啟動專案**
   ```bash
   python app.py
   ```
   瀏覽器開 <http://127.0.0.1:5000> 即可使用。

之後要改程式：先 `git pull` 拉最新 → 改完 → `git add .` → `git commit -m "說明"` → `git push`。

### 日常共編流程

| 誰 | 要做的事 |
|----|----------|
| **要改程式前** | 先拉最新：`git pull` |
| **改完後** | `git add .` → `git commit -m "做了什麼"` → `git push` |
| **對方有 push** | 自己改之前或改完後執行 `git pull`，有衝突再一起解。 |

建議：兩人盡量**不要同時改同一個檔案同一段**，可事先說好誰負責哪一塊（例如你負責後端、同學負責前端），或一人改完 push 後另一人再 pull 再改，可減少衝突。

### 其他共編方式（選用）

- **VS Code / Cursor Live Share**：一人開專案後邀請對方即時連線，可同時編輯同一份檔案，適合一起除錯或討論。
- **GitLab**：若學校或團隊用 GitLab，步驟同上，只是把 `github.com` 換成你們的 GitLab 網址即可。

---

## 通知擴充

目前「有變更」時僅在資料庫記錄並可於網頁上點「看差異」。若要改成 Email / Line / 推播通知，可在 `backend/scheduler.py` 的 `run_check_subscription` 中，於 `if last and last.content_hash != new_hash:` 區塊內加上發送邏輯（例如呼叫 SendGrid、Line Notify 等）。

最後更新：2026-04-30 by chenweifanhub
