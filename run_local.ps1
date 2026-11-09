# Chay FastAPI Automation Service truc tiep bang Python (khong can Docker)
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " KHOI DONG AI CONTENT AUTOMATION (CHE DO LOCAL)      " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

# Kiem tra file .env
if (-not (Test-Path ".env")) {
    Write-Host "[CANH BAO] Chua co file .env! Dang tao tu .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[HUONG DAN] Vui long kiem tra va dien key vao file .env truoc khi chay!" -ForegroundColor Red
} else {
    Write-Host "[OK] Da tim thay file .env." -ForegroundColor Green
}

# Thiet lap PYTHONPATH
$env:PYTHONPATH = Join-Path $scriptDir "python-service"

# Kiem tra dependencies
Write-Host "[INFO] Dang kiem tra thu vien..." -ForegroundColor Cyan
python -c "import fastapi, uvicorn, notion_client, requests, pydantic, httpx" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[CANH BAO] Dang cai dat thu vien con thieu..." -ForegroundColor Yellow
    python -m pip install -r "python-service/requirements.txt"
}

Write-Host "[SUCCESS] Khoi dong FastAPI tai: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "[DOCS] Swagger API Documentation: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "[STOP] Nhan Ctrl + C de dung server.`n" -ForegroundColor Gray

python -m uvicorn app.main:app --app-dir "$scriptDir/python-service" --host 127.0.0.1 --port 8000 --reload
