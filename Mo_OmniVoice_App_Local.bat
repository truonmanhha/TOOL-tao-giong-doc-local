@echo off
chcp 65001 >nul
cd /d "%~dp0"
title OmniVoice Native App Local

:: --- CHỐNG CHẠY 100% GPU VÀ CPU ---
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set NUMEXPR_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set VECLIB_MAX_THREADS=1
set CUDA_LAUNCH_BLOCKING=1

echo ========================================================
echo         OMNIVOICE APP LOCAL - NATIVE DESKTOP
echo ========================================================
echo.

if not exist ".venv" (
    echo [*] Dang tao moi truong ao Python...
    python -m venv .venv
)

call .venv\Scripts\activate

if not exist ".cache" mkdir ".cache"
if not exist ".cache\huggingface" mkdir ".cache\huggingface"
if not exist ".cache\torch" mkdir ".cache\torch"
if not exist "models" mkdir "models"

set HF_HOME=%~dp0.cache\huggingface
set HUGGINGFACE_HUB_CACHE=%~dp0.cache\huggingface\hub
set TRANSFORMERS_CACHE=%~dp0.cache\huggingface\transformers
set TORCH_HOME=%~dp0.cache\torch

python -c "import PySide6, sounddevice, soundfile, imageio_ffmpeg, pydub, torch, qdarktheme" >nul 2>&1
if errorlevel 1 (
    echo [*] Dang cai dat thu vien can thiet cho app native...
    python -m pip install PySide6 sounddevice soundfile imageio-ffmpeg pydub huggingface_hub pyqtdarktheme
    python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
    python -m pip install -e .
)

if not exist "%~dp0models\OmniVoice\config.json" (
    echo [*] Chua co model local. Dang tu dong tai 1 lan...
    python prepare_local_model.py
    if errorlevel 1 (
        echo [!] Tai model that bai. Kiem tra mang roi chay lai.
        pause
        exit /b 1
    )
)

if not exist "%~dp0models\whisper-large-v3-turbo\config.json" (
    echo [*] Dang tai Whisper model ASR de tu dong nghe file mau...
    python prepare_local_model.py --with-asr
)

set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1

echo [*] Dang mo native desktop app...
echo [*] Ban nay khong mo Chrome/Edge, khong dung cua so web.
echo [*] Tinh nang ASR da duoc BAT (tu dong nghe va dien transcript giong ban web).
echo [*] Neu ban bi tran RAM/VRAM hoac may yeu, hay sua file bat nay va them --no-asr
echo.

.venv\Scripts\python.exe omnivoice_qt_app.py --model "%~dp0models\OmniVoice" --asr-model "%~dp0models\whisper-large-v3-turbo" %*
pause
