@echo off
chcp 65001 > nul
title 301 Downloader - Public Internet Mode
cls
echo ========================================================
echo        301 Downloader - Public Internet Sharing Mode
echo   (Дэлхийн хаанаас ч бусад хүмүүс орох нийтийн горим)
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [АЛДАА] Python суугаагүй байна!
    pause
    exit /b
)

echo Сервер болон Нийтийн интернэт линкийг асааж байна...
echo Түр хүлээнэ үү...
echo.

python app.py --public

pause
