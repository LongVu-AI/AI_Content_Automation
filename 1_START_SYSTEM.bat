@echo off
chcp 65001 >nul
title KHOI DONG HE THONG - AI CONTENT AUTOMATION

echo ====================================================================
echo             KHOI DONG HE THONG AI CONTENT AUTOMATION
echo ====================================================================
echo.

:: 1. Kiem tra Docker Desktop
echo [1/3] Dang kiem tra Docker Desktop...
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Vui lòng bật Docker Desktop trước.
    echo.
    pause
    exit /b 1
)
echo [-] Docker Desktop dang hoat dong tot.
echo.

:: 2. Kiem tra file .env
echo [2/3] Dang kiem tra file cau hinh .env...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo.
        echo [i] Đã tạo file .env. Vui lòng mở file .env và điền Token Notion/Telegram trước khi chạy lại.
    ) else (
        echo.
        echo [!] Khong tim thay file .env va .env.example!
    )
    echo.
    pause
    exit /b 1
)
echo [-] File .env da co san.
echo.

:: 3. Khoi dong Docker compose
echo [3/3] Dang khoi dong he thong containers (FastAPI + n8n)...
docker compose up -d --build
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Co loi xay ra khi khoi dong container! Vui long kiem tra lai Docker.
    echo.
    pause
    exit /b 1
)

echo.
echo ====================================================================
echo Hệ thống đang khởi động. Vui lòng đợi 10 giây...
echo ====================================================================
timeout /t 10 /nobreak >nul 2>&1 || ping 127.0.0.1 -n 11 >nul

echo.
echo ====================================================================
echo KHOI DONG THANH CONG! CAC DICH VU SAN SANG:
echo ====================================================================
echo   - FastAPI: http://localhost:8000/docs
echo   - n8n: http://localhost:5678
echo ====================================================================
echo.
timeout /t 5
