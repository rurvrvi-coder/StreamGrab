# StreamGrab - Build Instructions

## Быстрая сборка

### Windows
```bash
# Запуск скрипта сборки
build.bat

# Или вручную:
pip install pyinstaller requests PyQt6 yt-dlp ffmpeg-python mutagen
pyinstaller StreamGrab.spec --clean --noconfirm
```

### Linux/macOS
```bash
# Сделать скрипт исполняемым
chmod +x build.sh

# Запуск
./build.sh

# Или вручную:
pip install pyinstaller requests PyQt6 yt-dlp ffmpeg-python mutagen
pyinstaller StreamGrab.spec --clean --noconfirm
```

## Структура сборки

```
dist/
└── StreamGrab/
    ├── StreamGrab.exe      # Главный исполняемый файл
    ├── resources/            # Ресурсы (иконки и т.д.)
    └── _internal/            # Зависимости Python
```

## Сборка портативной версии (1 файл)

### Windows
```bash
pyinstaller StreamGrab-onefile.spec --onefile --noconfirm
```
Результат: `dist/StreamGrab.exe` (один файл, ~200-400 MB)

## Требования

### Системные
- Python 3.8+
- Windows 7+ / Linux / macOS

### Python пакеты
```
requests>=2.28.0
PyQt6>=6.4.0
yt-dlp>=2024.0.0
ffmpeg-python>=0.2.0
mutagen>=1.47.0
pyinstaller>=6.0.0
```

### FFmpeg (требуется для yt-dlp)
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows - скачать с https://ffmpeg.org/download.html
# Добавить в PATH или положить рядом с exe
```

## Устранение проблем

### PyInstaller не видит модули
```bash
# Принудительно указать скрытые импорты
pyinstaller StreamGrab.spec --hidden-import=yt_dlp --hidden-import=mutagen
```

### FFmpeg не найден
```bash
# Указать путь к ffmpeg
set FFPROBE_PATH=C:\ffmpeg\bin\ffprobe.exe
set FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
```

### Ошибка памяти при сборке
```bash
# Увеличить лимит
pyinstaller StreamGrab.spec --windowed --upx-dir=/path/to/upx
```

## Размер итогового файла

| Тип сборки | Размер |
|-----------|--------|
| Папка (с зависимостями) | ~150-200 MB |
| Один файл (--onefile) | ~200-400 MB |

## Проверка работоспособности

```bash
# Запуск из папки dist
./dist/StreamGrab/StreamGrab.exe

# Или портативная версия
./dist/StreamGrab.exe
```

## Дополнительные опции PyInstaller

```bash
# Режим отладки
pyinstaller StreamGrab.spec --debug=all

# Создание .msi инсталлера (Windows)
pip install msistub
pyinstaller StreamGrab.spec --windows-msvcrt-runtime=installed

# Подпись кода (Windows)
signtool sign /f certificate.pfx /p password StreamGrab.exe
```

## Автоматическая сборка CI/CD

### GitHub Actions (.github/workflows/build.yml)
```yaml
name: Build

on:
  release:
    types: [created]

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt pyinstaller
      - name: Build
        run: pyinstaller StreamGrab.spec --noconfirm
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: StreamGrab
          path: dist/
```
