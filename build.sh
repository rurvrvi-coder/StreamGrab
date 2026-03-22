#!/bin/bash
# Скрипт сборки StreamGrab для Linux/macOS

set -e

echo "================================================"
echo "  StreamGrab - Build Script"
echo "================================================"
echo ""

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python не найден. Установите Python 3.8+"
    exit 1
fi

# Создание папок
mkdir -p build dist resources

echo "[1/4] Проверка зависимостей..."
if ! pip show pyinstaller &> /dev/null; then
    echo "    Установка PyInstaller..."
    pip install pyinstaller
fi

echo "[2/4] Установка зависимостей проекта..."
pip install requests PyQt6 yt-dlp ffmpeg-python mutagen

echo "[3/4] Сборка с PyInstaller..."
pyinstaller StreamGrab.spec --clean --noconfirm

echo "[4/4] Копирование ресурсов..."
cp -r resources/* dist/StreamGrab/resources/ 2>/dev/null || true

echo ""
echo "================================================"
echo "  Сборка завершена!"
echo "================================================"
echo ""
echo "Исполняемый файл: dist/StreamGrab/StreamGrab"
echo ""
echo "Для создания портативной версии (1 файл):"
echo "  pyinstaller StreamGrab.spec --onefile --noconfirm"
echo ""
