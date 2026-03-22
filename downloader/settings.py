"""Settings manager for StreamGrab - saves/loads configuration"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from datetime import datetime

from downloader.file_handler import FileCategory


DEFAULT_SETTINGS = {
    "version": "1.0.0",
    "paths": {
        "download_folder": str(Path.home() / "Downloads"),
        "category_folders": {
            "video": "Videos",
            "audio": "Music",
            "image": "Images",
            "document": "Documents",
            "archive": "Archives",
            "application": "Applications",
            "other": "Downloads",
        },
    },
    "download": {
        "max_concurrent": 10,
        "num_segments": 8,
        "use_segmentation": True,
        "min_size_for_segmentation_mb": 100,
        "default_format": "best",
        "default_quality": "best",
        "default_audio_format": "mp3",
        "speed_limit_kb": 0,
    },
    "notifications": {
        "enabled": True,
        "sound": True,
        "on_complete": True,
        "on_error": True,
    },
    "ui": {
        "theme": "light",
        "language": "ru",
        "window_width": 850,
        "window_height": 700,
        "show_speed": True,
        "show_eta": True,
        "auto_scroll": True,
    },
    "advanced": {
        "retry_count": 3,
        "retry_delay_sec": 5,
        "timeout_sec": 60,
        "chunk_size_kb": 64,
        "verify_ssl": True,
    },
}


@dataclass
class AppSettings:
    """Application settings"""

    # Paths
    download_folder: str = str(Path.home() / "Downloads")
    category_folders: dict = field(
        default_factory=lambda: DEFAULT_SETTINGS["paths"]["category_folders"].copy()
    )

    # Download settings
    max_concurrent: int = 10
    num_segments: int = 8
    use_segmentation: bool = True
    min_size_for_segmentation_mb: int = 100
    default_format: str = "best"
    default_quality: str = "best"
    default_audio_format: str = "mp3"
    speed_limit_kb: int = 0

    # Notifications
    notifications_enabled: bool = True
    notifications_sound: bool = True
    notify_on_complete: bool = True
    notify_on_error: bool = True

    # UI
    theme: str = "light"
    language: str = "ru"
    window_width: int = 850
    window_height: int = 700
    show_speed: bool = True
    show_eta: bool = True
    auto_scroll: bool = True

    # Advanced
    retry_count: int = 3
    retry_delay_sec: int = 5
    timeout_sec: int = 60
    chunk_size_kb: int = 64
    verify_ssl: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SettingsManager:
    """Manages application settings persistence"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self._config_path = Path(config_path)
        else:
            self._config_path = self._get_default_config_path()

        self._settings: Optional[AppSettings] = None
        self._loaded = False

    def _get_default_config_path(self) -> Path:
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", Path.home() / ".config"))
        else:
            base = Path.home() / ".config"

        config_dir = base / "StreamGrab"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "settings.json"

    @property
    def settings(self) -> AppSettings:
        if self._settings is None:
            self.load()
        return self._settings

    @property
    def config_path(self) -> Path:
        return self._config_path

    def load(self) -> AppSettings:
        """Load settings from JSON file"""
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self._settings = AppSettings.from_dict(data)
                self._loaded = True
                return self._settings

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Error loading settings: {e}, using defaults")
                self._settings = AppSettings()
                self._loaded = True
                return self._settings
        else:
            self._settings = AppSettings()
            self._loaded = True
            return self._settings

    def save(self, settings: Optional[AppSettings] = None) -> bool:
        """Save settings to JSON file"""
        if settings is None:
            settings = self._settings

        if settings is None:
            settings = self.load()

        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            data = settings.to_dict()
            data["_meta"] = {
                "version": DEFAULT_SETTINGS["version"],
                "saved_at": datetime.now().isoformat(),
                "app_version": "1.0.0",
            }

            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            self._settings = settings
            return True

        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def reset(self) -> AppSettings:
        """Reset settings to defaults"""
        self._settings = AppSettings()
        self.save()
        return self._settings

    def update(self, **kwargs) -> AppSettings:
        """Update specific settings"""
        settings = self.load()

        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
            else:
                print(f"Unknown setting: {key}")

        self.save(settings)
        return settings

    def get_category_folder(self, category: FileCategory) -> Path:
        """Get folder path for category"""
        settings = self.load()
        cat_name = category.value
        folder_name = settings.category_folders.get(cat_name, "Downloads")
        return Path(settings.download_folder) / folder_name

    def is_loaded(self) -> bool:
        return self._loaded


# Global settings instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager


def get_settings() -> AppSettings:
    return get_settings_manager().load()


def save_settings(settings: Optional[AppSettings] = None) -> bool:
    return get_settings_manager().save(settings)
