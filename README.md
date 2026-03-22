# StreamGrab

 ![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
 ![License](https://img.shields.io/badge/License-MIT-green.svg)
 ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
 ![PyInstaller](https://img.shields.io/badge/PyInstaller-Ready-orange.svg)

> Кроссплатформенный менеджер загрузок с поддержкой YouTube, Vimeo, VK и 1000+ других сайтов

 ![Downloads](https://img.shields.io/github/downloads/username/StreamGrab/total?style=flat-square)
 ![Last Commit](https://img.shields.io/github/last-commit/username/StreamGrab/main?style=flat-square)
 [![CI](https://github.com/username/StreamGrab/actions/workflows/build.yml/badge.svg)](https://github.com/username/StreamGrab/actions)

---

## Содержание

- [Возможности](#возможности)
- [Скриншоты](#скриншоты)
- [Быстрый старт](#быстрый-старт)
- [Установка](#установка)
- [Сборка из исходников](#сборка-из-исходников)
- [Примеры использования](#примеры-использования)
- [Структура проекта](#структура-проекта)
- [Зависимости](#зависимости)
- [FAQ](#faq)
- [Лицензия](#лицензия)

---

## Возможности

### 🎬 Мультиплатформенность
- **YouTube** (видео, плейлисты, Shorts)
- **Vimeo** (Pro, Premium)
- **VK Video**
- **Twitch** (стримы, клипы, VOD)
- **SoundCloud**
- **Dailymotion**
- **RuTube**
- **TikTok**
- **Instagram** (Reels, Stories)
- **Twitter/X** (видео из твитов)
- **Facebook** (видео)
- **1000+ других сайтов** через yt-dlp

### ⚡ Высокая производительность
- **10 одновременных загрузок** без потери скорости
- **Сегментированная загрузка** (>100MB файлы автоматически делятся на части)
- **Возобновление загрузок** после перезапуска приложения
- **Автоматическое определение** поддержки Range-запросов сервером

### 🎛 Гибкие настройки формата
| Формат | Описание |
|--------|----------|
| MP4 | Универсальный видеоформат |
| WebM | Открытый формат Google |
| MKV | Контейнер для высокого качества |
| MP3 | Аудио (извлечение из видео) |
| WAV | Без потерь, аудио |
| FLAC | Сжатие без потерь |
| M4A | AAC аудио |

### 🎯 Качество видео
- 4K (2160p)
- 1440p
- 1080p (Full HD)
- 720p (HD)
- 480p
- 360p
- 240p
- Best Available

### 📁 Автосортировка файлов
```
Downloads/
├── Videos/        # .mp4, .mkv, .webm
├── Music/         # .mp3, .wav, .flac
├── Images/        # .jpg, .png, .gif
├── Documents/     # .pdf, .doc, .txt
├── Archives/      # .zip, .rar, .7z
└── Applications/  # .exe, .msi, .apk
```

### 🔧 Дополнительные функции
- **Ограничение скорости** - контроль пропускной способности
- **Логирование** - полная история операций в файле
- **Обработка ошибок** - понятные сообщения для пользователя
- **Потокобезопасность** - стабильная работа с множеством загрузок
- **Прогресс-бары** - визуальное отслеживание
- **Система событий** - асинхронные обновления UI

---

## Скриншоты

### Главное окно
```
┌─────────────────────────────────────────────────────────────────┐
│  StreamGrab Pro                              Активных: 2/10  │
├─────────────────────────────────────────────────────────────────┤
│  Новая загрузка                                                  │
│  ┌──────────────────────────────────────────────────┐ [MP4▾]  │
│  │ https://www.youtube.com/watch?v=...              │ [Best▾]  │
│  └──────────────────────────────────────────────────┘ [Скачать]│
├─────────────────────────────────────────────────────────────────┤
│  📥 Загрузки                                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 🎬 Amazing Video Title                      ⬇  ✓       │    │
│  │    https://youtube.com/watch?v=...                   │    │
│  │    ████████████░░░░░░░░░░░░░  65% • 85MB/130MB    │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 🎵 Song Title - Artist                      ⬇  ✓       │    │
│  │    https://soundcloud.com/...                        │    │
│  │    ████████████████████░░░░  92% • 8.5MB/9.2MB     │    │
│  └─────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│  📁 ~/Downloads  [📂 Папка] [⚡ Сегментов: 8] [⚙]   [🗑]      │
│                                                   В очереди: 3  │
└─────────────────────────────────────────────────────────────────┘
```

### Диалог выбора качества
```
┌─────────────────────────────────┐
│     Выбор качества              │
├─────────────────────────────────┤
│  Video Title Here               │
│  Duration: 10:30 | YouTube      │
│                                 │
│  Формат:                        │
│  ○ MP4  ○ WebM  ○ MKV          │
│  ○ MP3  ○ WAV    ○ FLAC        │
│                                 │
│  Качество видео:                 │
│  ┌─────────────────────────┐    │
│  │ Best               ▾    │    │
│  │ 4K (2160p)            │    │
│  │ 1440p                  │    │
│  │ 1080p                  │    │
│  │ 720p                   │    │
│  └─────────────────────────┘    │
│                                 │
│            [Скачать] [Отмена]    │
└─────────────────────────────────┘
```

### Диалог настроек
```
┌─────────────────────────────────┐
│       Настройки                  │
├─────────────────────────────────┤
│  Базовая папка                  │
│  ┌─────────────────────────┐    │
│  │ ~/Downloads              │ 📂│
│  └─────────────────────────┘    │
│                                 │
│  Сегментация                     │
│  Количество сегментов: [8]       │
│  (для файлов > 100 MB)          │
│                                 │
│  Папки по категориям:            │
│  Videos:     ~/Downloads/Videos  │
│  Music:      ~/Downloads/Music   │
│  Images:     ~/Downloads/Images  │
│  Documents:  ~/Downloads/Docs   │
│  Archives:   ~/Downloads/Arcs   │
│                                 │
│       [Сохранить] [Отмена]       │
└─────────────────────────────────┘
```

---

## Быстрый старт

### Скачать готовый exe

1. Перейдите в [Releases](https://github.com/username/StreamGrab/releases)
2. Скачайте последнюю версию
3. Распакуйте и запустите `StreamGrab.exe`

### Запуск из исходников

```bash
# Клонирование репозитория
git clone https://github.com/username/StreamGrab.git
cd StreamGrab

# Установка зависимостей
pip install -r requirements.txt

# Запуск
python gui_tkinter.py
```

---

## Установка

### Требования

| Компонент | Минимум | Рекомендуется |
|----------|---------|---------------|
| Python | 3.8 | 3.10-3.11 |
| RAM | 512 MB | 2 GB |
| Диск | 500 MB | 1 GB |
| FFmpeg | Необязательно | Требуется для аудио |

### FFmpeg (опционально)

FFmpeg требуется для извлечения аудио и конвертации форматов.

**Windows:**
```powershell
# Скачать с https://ffmpeg.org/download.html
# Распаковать и добавить в PATH
# Или поместить ffmpeg.exe рядом с StreamGrab.exe
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### Установка Python зависимостей

```bash
pip install -r requirements.txt
```

Или вручную:
```bash
pip install requests PyQt6 yt-dlp ffmpeg-python mutagen
```

---

## Сборка из исходников

### Windows

```bash
# Откройте cmd или PowerShell в папке проекта

# Установите pyinstaller
pip install pyinstaller

# Сборка
pyinstaller StreamGrab.spec --clean --noconfirm

# Или используйте готовый скрипт
build.bat
```

Результат в `dist/StreamGrab/`

### Портативная версия (1 файл)

```bash
pyinstaller StreamGrab-onefile.spec --onefile --noconfirm
```

Результат: `dist/StreamGrab.exe` (~200-400 MB)

### Linux/macOS

```bash
# Сделайте скрипт исполняемым
chmod +x build.sh

# Запустите
./build.sh

# Или вручную
pip install pyinstaller
pyinstaller StreamGrab.spec --clean --noconfirm
```

### GitHub Actions (CI/CD)

Сборки автоматически создаются при каждом релизе:

1. Создайте тег: `git tag v1.0.0`
2. Отправьте: `git push origin v1.0.0`
3. Создайте Release на GitHub

Сборки появятся на странице Releases для Windows, Linux и macOS.

---

## Примеры использования

### Скачать видео YouTube в 1080p
1. Вставьте URL: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
2. Выберите формат: `MP4`
3. Выберите качество: `1080p`
4. Нажмите "Скачать"

### Извлечь аудио из видео
1. Вставьте URL видео
2. Выберите формат: `MP3`
3. Выберите качество: `Best`
4. Нажмите "Скачать"
5. Файл сохранится в папку `Music/`

### Скачать большой файл с сегментацией
1. Вставьте URL файла >100MB
2. Система автоматически определит поддержку сервером Range-запросов
3. Файл будет скачиваться в 8 потоков параллельно
4. В UI появится индикатор `⚡`

### Массовая загрузка
1. Добавьте первую ссылку
2. Не дожидаясь завершения, добавьте следующую
3. Повторите до 10 ссылок одновременно
4. Все загрузки пойдут параллельно

---

## Структура проекта

```
StreamGrab/
├── downloader/                      # Основной код загрузчика
│   ├── __init__.py                # Экспорт модулей
│   ├── models.py                  # Модели данных (Task, Status, etc.)
│   ├── events.py                  # EventEmitter для уведомлений
│   ├── logger.py                  # Логирование + ErrorHandler
│   ├── manager.py                  # DownloadManager (точка входа)
│   ├── thread_pool.py             # Пул потоков + планировщик
│   ├── url_parser.py              # Определение типа URL
│   ├── file_handler.py            # FileTypeDetector, FolderManager
│   ├── segmented_downloader.py     # Сегментированная загрузка
│   └── ytdlp_downloader.py       # yt-dlp обёртка
│
├── gui_tkinter.py                 # Tkinter GUI
├── gui_pyqt.py                    # PyQt6 GUI (опционально)
│
├── tests/                         # Тесты
│   ├── test_logger.py
│   ├── test_segmented.py
│   └── test_pool.py
│
├── resources/                     # Ресурсы
│   └── icon.ico                   # Иконка приложения
│
├── .github/workflows/             # CI/CD
│   └── build.yml
│
├── requirements.txt               # Python зависимости
├── setup.py                       # Установщик
├── pyproject.toml                 # Метаданные проекта
│
├── StreamGrab.spec             # PyInstaller config
├── StreamGrab-onefile.spec     # Портативная версия
├── build.bat                     # Скрипт сборки (Windows)
├── build.sh                      # Скрипт сборки (Linux/macOS)
│
├── BUILD_INSTRUCTIONS.md          # Подробная инструкция сборки
├── README.md                      # Этот файл
└── LICENSE                       # MIT License
```

---

## Зависимости

### Основные

| Пакет | Версия | Назначение |
|-------|--------|------------|
| `requests` | >=2.28 | HTTP-клиент |
| `PyQt6` | >=6.4 | Графический интерфейс |
| `yt-dlp` | >=2024.0 | Загрузка видео |
| `ffmpeg-python` | >=0.2 | FFmpeg обёртка |
| `mutagen` | >=1.47 | Метаданные аудио |
| `pyinstaller` | >=6.0 | Сборка в exe |

### Системные

| Пакет | Платформа | Назначение |
|-------|----------|------------|
| `ffmpeg` | Все | Конвертация видео/аудио |

### Установка всех зависимостей

```bash
pip install -r requirements.txt
```

requirements.txt:
```
requests>=2.28.0
PyQt6>=6.4.0
yt-dlp>=2024.0.0
ffmpeg-python>=0.2.0
mutagen>=1.47.0
pyinstaller>=6.0.0
```

---

## FAQ

### Q: Почему не скачивается видео с YouTube?
**A:** YouTube часто блокирует запросы. Убедитесь, что у вас стабильное интернет-соединение. Попробуйте использовать VPN или подождать несколько минут.

### Q: Требуется ли FFmpeg?
**A:** Для базовой загрузки видео - нет. FFmpeg нужен для: извлечения аудио (MP3/WAV), конвертации форматов, объединения потоков видео+аудио.

### Q: Как изменить папку загрузки по умолчанию?
**A:** Нажмите кнопку "📂 Папка" или "⚙" → Настройки → измените "Базовая папка".

### Q: Можно ли ограничить скорость загрузки?
**A:** Функция ограничения скорости доступна через API. В GUI можно добавить через диалог настроек.

### Q: Как восстановить прерванную загрузку?
**A:** Загрузки автоматически возобновляются. Если файл остался в папке с расширением `.part`, он будет дописан.

### Q: Сколько одновременных загрузок поддерживается?
**A:** По умолчанию 10. Можно изменить в настройках или при инициализации.

### Q: Какие форматы аудио поддерживаются?
**A:** MP3, WAV, FLAC, M4A, AAC, OGG, OPUS. Для извлечения требуется FFmpeg.

### Q: Приложение не запускается после сборки
**A:** Убедитесь, что FFmpeg доступен в PATH или лежит рядом с exe. Проверьте логи в `~/.StreamGrab/logs/`.

---

## Разработка

### Запуск тестов

```bash
# Все тесты
python -m pytest tests/ -v

# Отдельный тест
python tests/test_logger.py
python tests/test_segmented.py
python tests/test_pool.py
```

### Логи

Логи сохраняются в:
- Windows: `C:\Users\<user>\.StreamGrab\logs\`
- Linux/macOS: `~/.StreamGrab/logs/`

### Отладка

```bash
# Запуск с выводом отладки
python gui_tkinter.py --debug

# Или через переменную окружения
set PYTHONVERBOSE=1
python gui_tkinter.py
```

---

## Лицензия

Проект распространяется под лицензией **MIT License**.

```
MIT License

Copyright (c) 2024 StreamGrab

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Контакты

- **GitHub Issues**: https://github.com/username/StreamGrab/issues
- **Discussions**: https://github.com/username/StreamGrab/discussions

---

<p align="center">
  <strong>⭐ Не забудьте поставить звезду, если проект оказался полезным!</strong>
</p>
