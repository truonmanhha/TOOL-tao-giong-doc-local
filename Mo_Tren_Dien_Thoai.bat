@echo off
chcp 65001 >nul
cd /d "%~dp0"
title OmniVoice Pro Web (Mobile)

echo ========================================================
echo DANG MO GIAO DIEN WEB (CHO IPAD / DIEN THOAI)
echo ========================================================
echo.
echo Dang tim IP Local cua may tinh...

for /f "tokens=14" %%a in ('ipconfig ^| findstr IPv4') do set LOCAL_IP=%%a

echo.
echo IP cua ban la: %LOCAL_IP%
echo Hay mo trinh duyet tren iPad / Dien thoai va truy cap:
echo http://%LOCAL_IP%:7860
echo.
echo Vui long de cua so nay hoat dong de may tinh lam may chu.
echo ========================================================
echo.

.venv\Scripts\python.exe omnivoice_pro_ui.py --ip 0.0.0.0 --port 7860 --model "%~dp0models\OmniVoice" --asr-model "%~dp0models\whisper-large-v3-turbo" %*

pause
