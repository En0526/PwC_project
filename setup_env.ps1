# 訂閱網站更新監測系統 - 環境一鍵設定 (Windows PowerShell)
# 用法: 在 PowerShell 執行 .\setup_env.ps1

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

Write-Host "=== NTU_AI 環境設定 ===" -ForegroundColor Cyan
Set-Location $projectRoot

# 1. 建立虛擬環境（若不存在）
if (-not (Test-Path "venv")) {
    Write-Host "建立 venv..." -ForegroundColor Yellow
    python -m venv venv
} else {
    Write-Host "venv 已存在，略過建立。" -ForegroundColor Green
}

# 2. 啟動 venv 並安裝依賴
Write-Host "安裝套件 (requirements.txt)..." -ForegroundColor Yellow
& ".\venv\Scripts\pip.exe" install -r requirements.txt --quiet

# 3. 若沒有 .env 則從範例複製
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "已從 .env.example 建立 .env，請編輯 .env 設定 FLASK_SECRET_KEY 等。" -ForegroundColor Yellow
} else {
    Write-Host ".env 已存在，未覆寫。" -ForegroundColor Green
}

Write-Host ""
Write-Host "環境設定完成。接下來：" -ForegroundColor Green
Write-Host "  1. 若要啟動： venv\Scripts\activate 然後 python app.py"
Write-Host "  2. 或直接： .\venv\Scripts\python.exe app.py"
Write-Host ""
