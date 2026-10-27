@echo off
chcp 65001 > nul
title Cuu Nhi - Studio Video MP4 & Podcast Kinh Dich Chuyen Sau
echo =====================================================================
echo    CUU NHI - STUDIO VIDEO MP4 & PODCAST KINH DICH CHUYEN SAU
echo =====================================================================
echo Dang khoi dong Studio tai http://localhost:8000 ...
echo Vui long mo trinh duyet neu khong tu dong mo.
echo.

start "" "http://localhost:8000"
python web_app.py
pause
