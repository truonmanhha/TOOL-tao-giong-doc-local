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

:: --- PORTABLE UV: cache & python nam trong project (ko chay o C) ---
set UV_EXE=%~dp0.uv\bin\uv.exe
set UV_PYTHON_INSTALL_DIR=%~dp0.uv\python
set UV_CACHE_DIR=%~dp0.uv\cache
set UV_TOOL_DIR=%~dp0.uv\tools

:: Tu dong tai uv neu chua co (tai ve .uv\bin)
if not exist "%UV_EXE%" (
    echo [*] Dang tai uv ve project ^(1 lan duy nhat^)...
    if not exist "%~dp0.uv\bin" mkdir "%~dp0.uv\bin"
    powershell -Command "& { irm https://astral.sh/uv/install.ps1 | iex }" >nul 2>&1
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        copy "%USERPROFILE%\.local\bin\uv.exe" "%UV_EXE%" >nul
        copy "%USERPROFILE%\.local\bin\uvx.exe" "%~dp0.uv\bin\uvx.exe" >nul
    )
    if not exist "%UV_EXE%" (
        echo [!] Khong the tai uv. Hay chay lai hoac tai thu cong.
        pause
        exit /b 1
    )
)

:: Tao venv bang uv (tu dong download Python 3.10 ve .uv\python neu chua co)
if not exist ".venv" (
    echo [*] Dang tai Python va tao moi truong ao...
    "%UV_EXE%" venv --python 3.10 .venv
    if errorlevel 1 (
        echo [!] Tao venv that bai.
        pause
        exit /b 1
    )
) else if not exist ".venv\Scripts\python.exe" (
    echo [*] .venv bi loi, dang tao lai...
    rmdir /s /q ".venv"
    "%UV_EXE%" venv --python 3.10 .venv
    if errorlevel 1 (
        echo [!] Tao venv that bai.
        pause
        exit /b 1
    )
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
    "%UV_EXE%" pip install --python ".venv\Scripts\python.exe" PySide6 sounddevice soundfile imageio-ffmpeg pydub huggingface_hub pyqtdarktheme
    "%UV_EXE%" pip install --python ".venv\Scripts\python.exe" torch torchaudio --index-url https://download.pytorch.org/whl/cu128
    "%UV_EXE%" pip install --python ".venv\Scripts\python.exe" -e .
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
