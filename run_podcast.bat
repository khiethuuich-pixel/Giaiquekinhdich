@echo off
chcp 65001 > nul
title Cuu Nhi - Bang Moi: Studio Podcast & Video MP4 Chuyen Sau
echo =====================================================================
echo    CUU NHI - BANG MOI: STUDIO PODCAST ^& VIDEO MP4 CHUYEN SAU
echo =====================================================================
echo Dang khoi dong Bang Moi tai http://localhost:8000/podcast ...
echo.

start "" "http://localhost:8000/podcast"
python web_app.py
pause
