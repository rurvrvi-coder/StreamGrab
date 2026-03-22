"""Tests for settings module"""

import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from downloader.settings import (
    SettingsManager,
    AppSettings,
    DEFAULT_SETTINGS,
    get_settings_manager,
    get_settings,
    save_settings,
)
from downloader.file_handler import FileCategory


@pytest.fixture
def temp_config_dir():
    """Create temporary config directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_file(temp_config_dir):
    """Return path to temp config file"""
    config_path = temp_config_dir / "settings.json"
    return config_path


class TestAppSettings:
    """Tests for AppSettings dataclass"""

    def test_default_values(self):
        """Test default settings values"""
        settings = AppSettings()

        assert settings.max_concurrent == 10
        assert settings.num_segments == 8
        assert settings.use_segmentation is True
        assert settings.min_size_for_segmentation_mb == 100
        assert settings.notifications_enabled is True
        assert settings.download_folder == str(Path.home() / "Downloads")

    def test_custom_values(self):
        """Test custom settings values"""
        settings = AppSettings(
            max_concurrent=5,
            num_segments=4,
            notifications_enabled=False,
            download_folder="/custom/path",
        )

        assert settings.max_concurrent == 5
        assert settings.num_segments == 4
        assert settings.notifications_enabled is False
        assert settings.download_folder == "/custom/path"

    def test_to_dict(self):
        """Test converting settings to dictionary"""
        settings = AppSettings(max_concurrent=5)
        data = settings.to_dict()

        assert isinstance(data, dict)
        assert data["max_concurrent"] == 5
        assert "download_folder" in data

    def test_from_dict(self):
        """Test creating settings from dictionary"""
        data = {
            "download_folder": "/test/path",
            "max_concurrent": 3,
            "num_segments": 6,
            "notifications_enabled": False,
        }

        settings = AppSettings.from_dict(data)

        assert settings.download_folder == "/test/path"
        assert settings.max_concurrent == 3
        assert settings.num_segments == 6
        assert settings.notifications_enabled is False

    def test_from_dict_ignores_unknown_keys(self):
        """Test that from_dict ignores unknown keys"""
        data = {"max_concurrent": 3, "unknown_key": "value"}

        settings = AppSettings.from_dict(data)

        assert settings.max_concurrent == 3
        assert not hasattr(settings, "unknown_key")


class TestSettingsManager:
    """Tests for SettingsManager class"""

    def test_init_with_custom_path(self, temp_config_file):
        """Test initialization with custom config path"""
        manager = SettingsManager(str(temp_config_file))

        assert manager.config_path == temp_config_file

    def test_init_creates_default_path(self):
        """Test that default config path is created"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"APPDATA": tmpdir}):
                manager = SettingsManager()

                expected_path = Path(tmpdir) / "StreamGrab" / "settings.json"
                assert manager.config_path == expected_path

    def test_load_returns_default_when_no_file(self, temp_config_file):
        """Test loading returns defaults when file doesn't exist"""
        manager = SettingsManager(str(temp_config_file))
        settings = manager.load()

        assert isinstance(settings, AppSettings)
        assert settings.max_concurrent == DEFAULT_SETTINGS["download"]["max_concurrent"]

    def test_load_reads_existing_file(self, temp_config_file):
        """Test loading reads existing config file"""
        config_data = {
            "max_concurrent": 7,
            "num_segments": 12,
            "download_folder": "/custom/downloads",
        }

        with open(temp_config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        manager = SettingsManager(str(temp_config_file))
        settings = manager.load()

        assert settings.max_concurrent == 7
        assert settings.num_segments == 12
        assert settings.download_folder == "/custom/downloads"

    def test_load_handles_invalid_json(self, temp_config_file):
        """Test loading handles invalid JSON gracefully"""
        with open(temp_config_file, "w", encoding="utf-8") as f:
            f.write("invalid json {")

        manager = SettingsManager(str(temp_config_file))
        settings = manager.load()

        assert isinstance(settings, AppSettings)
        assert settings.max_concurrent == 10

    def test_save_creates_file(self, temp_config_file):
        """Test saving creates config file"""
        manager = SettingsManager(str(temp_config_file))
        settings = AppSettings(max_concurrent=8, num_segments=10)

        result = manager.save(settings)

        assert result is True
        assert temp_config_file.exists()

        with open(temp_config_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data["max_concurrent"] == 8
        assert saved_data["num_segments"] == 10

    def test_save_includes_metadata(self, temp_config_file):
        """Test saving includes metadata"""
        manager = SettingsManager(str(temp_config_file))
        settings = AppSettings()

        manager.save(settings)

        with open(temp_config_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        assert "_meta" in saved_data
        assert "version" in saved_data["_meta"]
        assert "saved_at" in saved_data["_meta"]

    def test_save_creates_parent_directory(self, temp_config_file):
        """Test saving creates parent directories"""
        manager = SettingsManager(str(temp_config_file))
        settings = AppSettings()

        result = manager.save(settings)

        assert result is True
        assert temp_config_file.parent.exists()

    def test_reset_restores_defaults(self, temp_config_file):
        """Test reset restores default settings"""
        manager = SettingsManager(str(temp_config_file))
        settings = AppSettings(max_concurrent=99, num_segments=99)
        manager.save(settings)

        manager.reset()
        loaded = manager.load()

        assert loaded.max_concurrent == 10
        assert loaded.num_segments == 8

    def test_update_modifies_specific_settings(self, temp_config_file):
        """Test updating specific settings"""
        manager = SettingsManager(str(temp_config_file))

        manager.update(max_concurrent=15, num_segments=12)
        settings = manager.load()

        assert settings.max_concurrent == 15
        assert settings.num_segments == 12

    def test_update_ignores_unknown_keys(self, temp_config_file):
        """Test update ignores unknown keys"""
        manager = SettingsManager(str(temp_config_file))

        manager.update(unknown_key="value")
        settings = manager.load()

        assert not hasattr(settings, "unknown_key")

    def test_get_category_folder(self, temp_config_file):
        """Test getting category folder path"""
        manager = SettingsManager(str(temp_config_file))
        manager.update(
            download_folder="/downloads", category_folders={"video": "MyVideos"}
        )

        folder = manager.get_category_folder(FileCategory.VIDEO)

        assert folder == Path("/downloads/MyVideos")

    def test_settings_property_loads_if_needed(self, temp_config_file):
        """Test settings property loads if not loaded"""
        manager = SettingsManager(str(temp_config_file))

        settings = manager.settings

        assert isinstance(settings, AppSettings)
        assert manager.is_loaded() is True

    def test_settings_property_returns_cached(self, temp_config_file):
        """Test settings property returns cached value"""
        manager = SettingsManager(str(temp_config_file))
        manager.settings

        settings1 = manager.settings
        settings2 = manager.settings

        assert settings1 is settings2


class TestGlobalFunctions:
    """Tests for global helper functions"""

    def test_get_settings_manager_returns_singleton(self):
        """Test get_settings_manager returns same instance"""
        global _settings_manager

        from downloader.settings import _settings_manager

        if _settings_manager:
            _settings_manager = None

        manager1 = get_settings_manager()
        manager2 = get_settings_manager()

        assert manager1 is manager2

    def test_get_settings_returns_app_settings(self):
        """Test get_settings returns AppSettings instance"""
        settings = get_settings()

        assert isinstance(settings, AppSettings)

    def test_save_settings_works(self, temp_config_file):
        """Test save_settings global function works"""
        manager = SettingsManager(str(temp_config_file))
        settings = AppSettings(max_concurrent=7)

        result = save_settings(settings)

        assert result is True
        loaded = manager.load()
        assert loaded.max_concurrent == 7


class TestSettingsIntegration:
    """Integration tests for settings"""

    def test_full_save_load_cycle(self, temp_config_file):
        """Test complete save-load cycle"""
        original = AppSettings(
            max_concurrent=5,
            num_segments=4,
            notifications_enabled=False,
            download_folder="/test/downloads",
            category_folders={"video": "CustomVideos"},
        )

        manager = SettingsManager(str(temp_config_file))
        manager.save(original)

        loaded = manager.load()

        assert loaded.max_concurrent == original.max_concurrent
        assert loaded.num_segments == original.num_segments
        assert loaded.notifications_enabled == original.notifications_enabled
        assert loaded.download_folder == original.download_folder
        assert loaded.category_folders == original.category_folders

    def test_partial_update_preserves_other_values(self, temp_config_file):
        """Test partial update preserves other values"""
        manager = SettingsManager(str(temp_config_file))
        manager.update(max_concurrent=20, notifications_enabled=False)

        loaded = manager.load()

        assert loaded.max_concurrent == 20
        assert loaded.notifications_enabled is False
        assert loaded.num_segments == 8
        assert loaded.download_folder == str(Path.home() / "Downloads")
