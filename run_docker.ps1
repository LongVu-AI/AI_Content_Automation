# Chay he thong bang Docker Compose
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " KHOI DONG AI AUTOMATION BANG DOCKER COMPOSE         " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

# Kiem tra Docker Desktop
docker ps 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[LOI] Docker Desktop chua bat! Vui long mo Docker Desktop truoc khi chay." -ForegroundColor Red
    Write-Host "[GOI Y] Ban co the dung script 'run_local.ps1' de chay nhanh bang Python ma khong can Docker!" -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] Docker dang hoat dong. Dang build va khoi dong container..." -ForegroundColor Cyan
docker compose up -d --build

Write-Host "`n[SUCCESS] Stack Docker da khoi dong thanh cong!" -ForegroundColor Green
Write-Host "- FastAPI: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "- n8n:     http://127.0.0.1:5678" -ForegroundColor Green
