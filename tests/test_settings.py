"""Tests for settings module"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from downloader.settings import SettingsManager, AppSettings


@pytest.fixture
def temp_config_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "settings.json"


class TestAppSettings:
    def test_default_values(self):
        settings = AppSettings()
        assert settings.max_concurrent == 10
        assert settings.num_segments == 8
        assert settings.notifications_enabled is True

    def test_custom_values(self):
        settings = AppSettings(max_concurrent=5, num_segments=4)
        assert settings.max_concurrent == 5
        assert settings.num_segments == 4

    def test_to_dict(self):
        settings = AppSettings()
        data = settings.to_dict()
        assert isinstance(data, dict)
        assert "max_concurrent" in data

    def test_from_dict(self):
        data = {"max_concurrent": 7, "num_segments": 12}
        settings = AppSettings.from_dict(data)
        assert settings.max_concurrent == 7
        assert settings.num_segments == 12


class TestSettingsManager:
    def test_init_with_custom_path(self, temp_config_file):
        manager = SettingsManager(str(temp_config_file))
        assert manager.config_path == temp_config_file

    def test_load_returns_default_when_no_file(self, temp_config_file):
        manager = SettingsManager(str(temp_config_file))
        settings = manager.load()
        assert isinstance(settings, AppSettings)

    def test_save_creates_file(self, temp_config_file):
        manager = SettingsManager(str(temp_config_file))
        settings = AppSettings(max_concurrent=8)
        result = manager.save(settings)
        assert result is True
        assert temp_config_file.exists()

    def test_reset_restores_defaults(self, temp_config_file):
        manager = SettingsManager(str(temp_config_file))
        settings = AppSettings(max_concurrent=99)
        manager.save(settings)
        manager.reset()
        loaded = manager.load()
        assert loaded.max_concurrent == 10
