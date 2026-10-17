@echo off
chcp 65001 >nul
title NGROK TUNNEL - AI CONTENT AUTOMATION

echo ====================================================================
echo            KHOI DONG NGROK TUNNEL CHO FASTAPI (PORT 8000)
echo ====================================================================
echo.
echo Copy URL https ở đây để dán vào Telegram/TikTok
echo Vui lòng giữ cửa sổ này luôn mở trong suốt quá trình test!
echo.
echo ====================================================================
echo.

ngrok http 8000
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Khong the khoi dong ngrok. Vui long kiem tra xem ngrok da duoc cai dat hay chua.
    echo Co the tai ngrok tai: https://ngrok.com/download
    echo.
    pause
)

