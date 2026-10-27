@echo off
chcp 65001 > nul
title Cuu Nhi - Luan Truc Tiep & Ghi Am Full Phan Tich Gemini (9:16)
echo =====================================================================
echo    CUU NHI - LUAN TRUC TIEP ^& GHI AM FULL PHAN TICH GEMINI (9:16)
echo =====================================================================
echo Dang khoi dong tai http://localhost:8000/direct-full ...
echo.

start "" "http://localhost:8000/direct-full"
python web_app.py
pause
