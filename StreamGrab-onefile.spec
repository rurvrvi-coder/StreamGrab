# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File для StreamGrab - OneFile Portable Version
Создает ОДИН .exe файл без зависимостей
"""

import os
from pathlib import Path

block_cipher = None

project_root = Path.cwd()
icon_path = project_root / "resources" / "icon.ico"

a = Analysis(
    ["gui_tkinter.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "downloader"), "downloader"),
    ],
    hiddenimports=[
        "yt_dlp",
        "yt_dlp.utils",
        "yt_dlp.extractor",
        "yt_dlp.extractor._extractors",
        "yt_dlp.extractor.youtube",
        "yt_dlp.extractor.vimeo",
        "yt_dlp.extractor.vkontakte",
        "yt_dlp.extractor.dailymotion",
        "yt_dlp.extractor.twitch",
        "yt_dlp.extractor.soundcloud",
        "yt_dlp.extractor.bandcamp",
        "yt_dlp.extractor.rutube",
        "yt_dlp.extractor.common",
        "yt_dlp.extractor.generic",
        "yt_dlp.downloader",
        "yt_dlp.downloader.common",
        "yt_dlp.downloader.http",
        "yt_dlp.postprocessor",
        "yt_dlp.postprocessor.ffmpeg",
        "requests",
        "urllib3",
        "charset_normalizer",
        "idna",
        "certifi",
        "brotli",
        "websockets",
        "mutagen",
        "mutagen.mp3",
        "mutagen.mp4",
        "mutagen.flac",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "plyer",
        "plyer.facades",
        "plyer.notification",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy",
        "scipy",
        "PIL",
        "tkinter.test",
        "unittest",
        "xmlrpc",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StreamGrab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_path) if icon_path.exists() else None,
    version=None,
)
