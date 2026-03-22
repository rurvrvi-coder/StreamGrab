"""Basic tests for StreamGrab"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestURLParser:
    """Test URL parsing functionality"""

    def test_youtube_url(self):
        from downloader.url_parser import URLParser

        assert URLParser.is_supported_video("https://www.youtube.com/watch?v=test")
        assert URLParser.is_supported_video("https://youtu.be/test")

    def test_vimeo_url(self):
        from downloader.url_parser import URLParser

        assert URLParser.is_supported_video("https://vimeo.com/123456789")

    def test_invalid_url(self):
        from downloader.url_parser import URLParser

        assert not URLParser.is_valid_url("not a url")
        assert not URLParser.is_valid_url("")


class TestFileHandler:
    """Test file handling functionality"""

    def test_file_type_detection(self):
        from downloader.file_handler import FileTypeDetector

        cat, ext, mime = FileTypeDetector.detect_from_url(
            "https://example.com/video.mp4"
        )
        assert cat.value == "video"
        assert ext == ".mp4"

    def test_folder_manager(self):
        from downloader.file_handler import FolderManager

        fm = FolderManager()
        assert fm.base_path.exists() or fm.base_path == Path.home() / "Downloads"


class TestModels:
    """Test data models"""

    def test_download_task(self):
        from downloader.models import DownloadTask, Status
        from pathlib import Path

        task = DownloadTask(
            id="test_1",
            url="https://example.com/file.mp4",
            dest_path=Path("/tmp/test.mp4"),
        )
        assert task.url == "https://example.com/file.mp4"
        assert task.status == Status.PENDING

    def test_file_category(self):
        from downloader.models import FileCategory

        assert FileCategory.VIDEO.value == "video"
        assert FileCategory.AUDIO.value == "audio"


class TestThreadPool:
    """Test thread pool"""

    def test_thread_pool_creation(self):
        from downloader.thread_pool import ThreadPool

        pool = ThreadPool(num_workers=5)
        assert pool.get_active_count() == 0
        pool.shutdown()

    def test_download_job(self):
        from downloader.thread_pool import DownloadJob, TaskPriority

        job = DownloadJob(
            priority=TaskPriority.NORMAL.value,
            task_id="test_1",
            url="https://example.com/file.mp4",
            dest="/tmp/test.mp4",
            speed_limit=0,
            download_type="http",
            video_format=None,
            video_quality=None,
        )
        assert job.task_id == "test_1"


class TestSettings:
    """Test settings functionality"""

    def test_settings_default(self):
        from downloader.settings import AppSettings

        settings = AppSettings()
        assert settings.max_concurrent == 10
        assert settings.num_segments == 8

    def test_settings_to_dict(self):
        from downloader.settings import AppSettings

        settings = AppSettings()
        data = settings.to_dict()
        assert isinstance(data, dict)
        assert "max_concurrent" in data
