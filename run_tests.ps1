# Chay bo kiem thu tu dong 10 bai test
$ErrorActionPreference = "Continue"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " CHAY BO TEST TU DONG KIEM TRA HE THONG (10 TESTS)    " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

$env:PYTHONPATH = Join-Path $scriptDir "python-service"

python "tests/test_fixes.py"
