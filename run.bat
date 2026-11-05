@echo off
chcp 65001 > nul
title 301 Downloader - Universal Media Downloader
cls
echo ========================================================
echo        301 Downloader - Web Media Downloader
echo   (YouTube, Facebook, Instagram, TikTok MP4/MP3)
echo ========================================================
echo.

:: Check python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [АЛДАА] Python суугаагүй байна! 
    echo https://www.python.org/downloads/ хаягаас суулгана уу.
    pause
    exit /b
)

echo Серверийг асааж байна...
echo Вэб хөтөч (Browser) автоматаар нээгдэнэ...
echo.

python app.py

pause
