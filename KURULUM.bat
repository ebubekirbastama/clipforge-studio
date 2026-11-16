@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Short Studio - Kurulum

echo =============================================
echo     SHORT STUDIO - SES + VIDEO KURULUMU
echo =============================================
echo.
set "PY_CMD=python"
where py >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
%PY_CMD% --version >nul 2>&1
if errorlevel 1 (
    echo HATA: Python 3 yüklü degil. https://python.org/downloads
    pause
    exit /b 1
)
echo [1/4] Arayuz paketi kuruluyor...
%PY_CMD% -m pip install --upgrade "customtkinter>=5.2,<6"
if errorlevel 1 goto error
echo [2/4] Ses temizleme kutuphaneleri kuruluyor...
echo AI ozelligi icin Torch ve Demucs kurulumu buyuk boyutludur.
%PY_CMD% -m pip install torch demucs soundfile numpy
if errorlevel 1 goto error
echo [3/4] C surucusundeki FFmpeg kontrol ediliyor...
set "FFDIR="
if exist "C:\ffmpeg\bin\ffmpeg.exe" if exist "C:\ffprobe.exe" set "FFDIR=C:\ffmpeg\bin"
if not defined FFDIR if exist "C:\ffmpeg.exe" if exist "C:\ffprobe.exe" set "FFDIR=C:\ffmpeg"
if not defined FFDIR if exist "C:\ffmpeg.exe" if exist "C:\ffprobe.exe" set "FFDIR=C:\"
if not defined FFDIR (
    echo UYARI: C:\ffmpeg.exe ve ffprobe.exe bulunamadi.
    echo FFmpeg otomatik indirilmez. Dosyalari elle yerlestirin.
) else (
    echo FFmpeg bulundu: %FFDIR%
)
echo [4/4] Kurulum tamamlandi.
echo Baslatmak icin short_bolucu.pyw dosyasina cift tiklayin.
echo.
pause
exit /b 0
:error
echo.
echo HATA: Python paket kurulumu tamamlanamadi.
echo Internet baglantisini ve Python surumunu kontrol edin.
pause
exit /b 1
