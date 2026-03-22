# Скрипт сборки ytDownloader для Windows

@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ================================================
echo   ytDownloader - Build Script
echo ================================================
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден. Установите Python 3.8+
    pause
    exit /b 1
)

REM Создание папок
if not exist "build" mkdir build
if not exist "dist" mkdir dist
if not exist "resources" mkdir resources

echo [1/4] Проверка зависимостей...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo    Установка PyInstaller...
    pip install pyinstaller
)

echo [2/4] Установка зависимостей проекта...
pip install -q requests PyQt6 yt-dlp ffmpeg-python mutagen

echo [3/4] Сборка с PyInstaller...
pyinstaller ytDownloader.spec --clean --noconfirm

if errorlevel 1 (
    echo [ERROR] Ошибка сборки
    pause
    exit /b 1
)

echo [4/4] Копирование ресурсов...
xcopy /E /Y "resources\*" "dist\ytDownloader\resources\" >nul 2>&1

echo.
echo ================================================
echo   Сборка завершена!
echo ================================================
echo.
echo Исполняемый файл: dist\ytDownloader\ytDownloader.exe
echo.
echo Для создания портативной версии (1 файл):
echo   pyinstaller ytDownloader.spec --onefile --noconfirm
echo.
pause
