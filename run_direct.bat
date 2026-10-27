@echo off
chcp 65001 > nul
title Cuu Nhi - Bang Cu: Luan Truc Tiep (Video Doc 9:16)
echo =====================================================================
echo    CUU NHI - BANG CU: LUAN GIAI TRUC TIEP ^& VIDEO DOC 9:16
echo =====================================================================
echo Dang khoi dong Bang Cu tai http://localhost:8000/direct ...
echo.

start "" "http://localhost:8000/direct"
python web_app.py
pause
