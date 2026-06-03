@echo off
chcp 65001 >nul
title Don dep cache OmniVoice cu

echo ========================================================
echo              DON DEP CACHE TAI VE CU
echo ========================================================
echo.
echo Script nay se xoa cache HuggingFace mac dinh o user profile
echo de tranh viec model nam lan lung tung va an o dia.
echo.
set /p CONFIRM=Nhap Y roi Enter neu muon xoa: 
if /I not "%CONFIRM%"=="Y" (
    echo Da huy.
    pause
    exit /b 0
)

if exist "%USERPROFILE%\.cache\huggingface" (
    rmdir /s /q "%USERPROFILE%\.cache\huggingface"
    echo Da xoa: %USERPROFILE%\.cache\huggingface
) else (
    echo Khong thay cache cu de xoa.
)

echo.
echo Tu gio cache moi se nam trong thu muc .cache cua project nay.
pause
