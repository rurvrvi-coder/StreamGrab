# Инструкция по тестированию и релизу StreamGrab

## Тестирование

### Локальное тестирование (Windows)

```powershell
# 1. Запустите тест производительности
python scripts/test_concurrent.py

# 2. Ожидаемый результат:
# - Thread Pool Limits: PASS (10 потоков)
# - Task Cancellation: PASS
# - Settings Persistence: PASS
# - Concurrent Downloads: PASS (10 одновременных)
# - Speed Stability: PASS
# - Segmented Download: PASS (150MB файл)
```

### Тестирование сборки

```powershell
# 1. Сборка
powershell -ExecutionPolicy Bypass -File build.ps1 -All

# 2. Запуск тестов
python scripts/test_concurrent.py

# 3. Ручное тестирование:
#    - Запустите dist/StreamGrab.exe
#    - Добавьте 10 URL для загрузки
#    - Проверьте скорость и прогресс
```

## Создание релиза

### 1. Подготовка

```bash
# Обновите версию в settings.py
# Обновите changelog в README.md
# Проверьте все тесты проходят
```

### 2. Тегирование

```bash
# Создайте тег версии
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### 3. GitHub Actions автоматически:

1. Запустит линтер и тесты
2. Соберет Windows exe (folder + onefile)
3. Соберет Linux binary
4. Соберет macOS app
5. Создаст Release с артефактами

### 4. Проверка релиза

После сборки в GitHub:
- Скачайте `StreamGrab.exe` (portable)
- Скачайте `StreamGrab/` (folder version)
- Проверьте работоспособность

## Ручная сборка (если GitHub Actions недоступен)

### Windows

```powershell
# Установите зависимости
pip install pyinstaller requests yt-dlp mutagen plyer

# Сборка folder version
pyinstaller StreamGrab.spec --clean --noconfirm

# Сборка onefile
pyinstaller StreamGrab-onefile.spec --onefile --noconfirm
```

### macOS

```bash
# Установите зависимости
brew install ffmpeg
pip install pyinstaller requests yt-dlp mutagen plyer

# Сборка
pyinstaller StreamGrab.spec --clean --noconfirm
pyinstaller StreamGrab-onefile.spec --onefile --noconfirm
```

## Тесты производительности

| Тест | Ожидание | Статус |
|------|----------|--------|
| 10 concurrent downloads | Все 10 активны | |
| Speed stability | Variance < 50% | |
| Large file (150MB) | Без ошибок | |
| Settings save/load | Корректно | |
| Task cancellation | Работает | |

## Проверка onefile exe

1. Скопируйте `StreamGrab.exe` в отдельную папку
2. Запустите без установки
3. Проверьте:
   - GUI открывается
   - Загрузки работают
   - Настройки сохраняются
   - Ярлык на рабочем столе не требуется

## Troubleshooting

### "Failed to execute script"

```powershell
# Проверьте все hidden imports в spec файле
# Добавьте недостающие модули в hiddenimports
```

### Медленная загрузка

- Проверьте интернет-соединение
- Отключите VPN
- Попробуйте меньше одновременных загрузок

### Import errors при сборке

```python
# Добавьте в hiddenimports в spec файле:
"yt_dlp",
"yt_dlp.extractor",
# и т.д.
```
