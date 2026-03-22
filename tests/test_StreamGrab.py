"""Comprehensive tests for StreamGrab with mocks"""

import os
import sys
import time
import threading
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open, call
from dataclasses import dataclass
from io import BytesIO

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from downloader.models import (
    DownloadTask,
    Status,
    FileCategory,
    VideoFormat,
    VideoQuality,
    DownloadType,
)
from downloader.url_parser import URLParser
from downloader.file_handler import FileTypeDetector, FolderManager
from downloader.events import EventEmitter, EventType
from downloader.thread_pool import (
    ThreadPool,
    DownloadScheduler,
    DownloadJob,
    TaskPriority,
)
from downloader.segmented_downloader import (
    SegmentDownloader,
    SegmentedDownloadManager,
    DownloadSegment,
)


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_logger():
    """Mock logger for tests"""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def mock_responses():
    """Mock requests.Response for network tests"""
    response = Mock()
    response.status_code = 200
    response.headers = {
        "Content-Length": "1048576",
        "Content-Type": "application/octet-stream",
        "Accept-Ranges": "bytes",
    }
    response.iter_content = Mock(return_value=[b"chunk"] * 1024)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    return response


# ══════════════════════════════════════════════════════════════════════════════
# TEST: URL Parser
# ══════════════════════════════════════════════════════════════════════════════


class TestURLParser:
    """Tests for URLParser class"""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=abc123", True),
            ("https://youtu.be/abc123", True),
            ("https://youtube.com/shorts/abc123", True),
            ("https://m.youtube.com/watch?v=abc123", True),
            ("https://music.youtube.com/watch?v=abc123", True),
        ],
    )
    def test_youtube_urls(self, url, expected):
        assert URLParser.is_supported_video(url) == expected

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://vimeo.com/123456789", True),
            ("https://www.vimeo.com/123456789", True),
            ("https://vk.com/video123_456", True),
            ("https://vkontakte.ru/video123_456", True),
            ("https://www.twitch.tv/videos/123456", True),
            ("https://soundcloud.com/artist/track", True),
            ("https://www.soundcloud.com/artist/track", True),
            ("https://dailymotion.com/video/xyz", True),
            ("https://rutube.ru/video/123", True),
            ("https://ok.ru/video/123", True),
        ],
    )
    def test_other_video_platforms(self, url, expected):
        assert URLParser.is_supported_video(url) == expected

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://example.com/file.zip", False),
            ("https://example.com/document.pdf", False),
            ("https://example.com/image.jpg", False),
            ("https://not-a-site.com/video", False),
        ],
    )
    def test_non_video_urls(self, url, expected):
        assert URLParser.is_supported_video(url) == expected

    def test_get_platform_name_youtube(self):
        assert (
            URLParser.get_platform_name("https://youtube.com/watch?v=abc") == "YouTube"
        )
        assert URLParser.get_platform_name("https://youtu.be/abc") == "YouTube"

    def test_get_platform_name_vk(self):
        assert URLParser.get_platform_name("https://vk.com/video123") == "VK"

    def test_get_platform_name_unknown(self):
        assert URLParser.get_platform_name("https://unknown.com/video") is None

    def test_is_youtube_playlist(self):
        assert (
            URLParser.is_youtube_playlist("https://youtube.com/playlist?list=abc")
            is True
        )
        assert (
            URLParser.is_youtube_playlist("https://youtube.com/watch?v=xyz&list=abc")
            is True
        )
        assert URLParser.is_youtube_playlist("https://youtube.com/watch?v=xyz") is False

    def test_is_youtube_shorts(self):
        assert URLParser.is_youtube_shorts("https://youtube.com/shorts/abc123") is True
        assert URLParser.is_youtube_shorts("https://youtube.com/watch?v=abc") is False

    def test_get_download_type_video(self):
        assert (
            URLParser.get_download_type("https://youtube.com/watch?v=abc")
            == DownloadType.VIDEO
        )

    def test_get_download_type_http(self):
        assert (
            URLParser.get_download_type("https://example.com/file.zip")
            == DownloadType.HTTP
        )

    @pytest.mark.parametrize(
        "url,is_valid",
        [
            ("https://example.com/file.zip", True),
            ("http://example.com/file.zip", True),
            ("https://www.youtube.com/watch?v=abc", True),
            ("not-a-url", False),
            ("ftp://example.com/file", False),
            ("", False),
        ],
    )
    def test_is_valid_url(self, url, is_valid):
        assert URLParser.is_valid_url(url) == is_valid

    def test_sanitize_filename(self):
        assert URLParser.sanitize_filename("normal_file.txt") == "normal_file.txt"
        assert (
            URLParser.sanitize_filename("file<with>invalid:chars.txt")
            == "file_with_invalid_chars.txt"
        )
        assert URLParser.sanitize_filename("a" * 300 + ".txt") == "a" * 200
        assert URLParser.sanitize_filename("") == "download"

    def test_get_format_string_best(self):
        result = URLParser.get_format_string(None, None)
        assert result == "best"

    def test_get_format_string_with_quality(self):
        result = URLParser.get_format_string(VideoFormat.MP4, VideoQuality.QUALITY_1080)
        assert result == "1080+mp4"


# ══════════════════════════════════════════════════════════════════════════════
# TEST: File Type Detector
# ══════════════════════════════════════════════════════════════════════════════


class TestFileTypeDetector:
    """Tests for FileTypeDetector class"""

    @pytest.mark.parametrize(
        "url,expected_category,expected_folder",
        [
            ("https://example.com/video.mp4", FileCategory.VIDEO, "Videos"),
            ("https://example.com/video.webm", FileCategory.VIDEO, "Videos"),
            ("https://example.com/video.mkv", FileCategory.VIDEO, "Videos"),
            ("https://example.com/song.mp3", FileCategory.AUDIO, "Music"),
            ("https://example.com/song.wav", FileCategory.AUDIO, "Music"),
            ("https://example.com/song.flac", FileCategory.AUDIO, "Music"),
            ("https://example.com/image.jpg", FileCategory.IMAGE, "Images"),
            ("https://example.com/image.png", FileCategory.IMAGE, "Images"),
            ("https://example.com/doc.pdf", FileCategory.DOCUMENT, "Documents"),
            ("https://example.com/archive.zip", FileCategory.ARCHIVE, "Archives"),
            ("https://example.com/app.exe", FileCategory.APPLICATION, "Applications"),
        ],
    )
    def test_detect_from_url(self, url, expected_category, expected_folder):
        category, ext, folder = FileTypeDetector.detect_from_url(url)
        assert category == expected_category
        assert folder == expected_folder

    @pytest.mark.parametrize(
        "content_type,expected_category",
        [
            ("video/mp4", FileCategory.VIDEO),
            ("audio/mpeg", FileCategory.AUDIO),
            ("image/png", FileCategory.IMAGE),
            ("application/pdf", FileCategory.DOCUMENT),
            ("application/zip", FileCategory.ARCHIVE),
            ("application/octet-stream", FileCategory.APPLICATION),
        ],
    )
    def test_detect_from_content_type(self, content_type, expected_category):
        category, ext, folder = FileTypeDetector.detect_from_content_type(content_type)
        assert category == expected_category

    def test_detect_from_content_type_unknown(self):
        category, ext, folder = FileTypeDetector.detect_from_content_type(
            "unknown/type"
        )
        assert category == FileCategory.OTHER

    def test_detect_from_extension(self):
        category, mime = FileTypeDetector.detect_from_extension(".mp4")
        assert category == FileCategory.VIDEO
        assert mime == "video/mp4"

    def test_detect_from_extension_no_dot(self):
        category, mime = FileTypeDetector.detect_from_extension("mp4")
        assert category == FileCategory.VIDEO

    def test_detect_from_extension_unknown(self):
        category, mime = FileTypeDetector.detect_from_extension(".xyz")
        assert category == FileCategory.OTHER

    def test_get_category_folder(self):
        assert FileTypeDetector.get_category_folder(FileCategory.VIDEO) == "Videos"
        assert FileTypeDetector.get_category_folder(FileCategory.AUDIO) == "Music"
        assert FileTypeDetector.get_category_folder(FileCategory.IMAGE) == "Images"
        assert (
            FileTypeDetector.get_category_folder(FileCategory.DOCUMENT) == "Documents"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Folder Manager
# ══════════════════════════════════════════════════════════════════════════════


class TestFolderManager:
    """Tests for FolderManager class"""

    def test_folder_creation(self, temp_dir):
        manager = FolderManager(str(temp_dir))
        assert manager.base_path == temp_dir
        assert temp_dir.exists()

    def test_category_folders_created(self, temp_dir):
        manager = FolderManager(str(temp_dir))
        for cat in FileCategory:
            folder = manager.get_folder(cat)
            assert folder.exists()
            assert temp_dir in folder.parents

    def test_get_folder_video(self, temp_dir):
        manager = FolderManager(str(temp_dir))
        folder = manager.get_folder(FileCategory.VIDEO)
        assert "Videos" in str(folder)

    def test_get_folder_for_url(self, temp_dir):
        manager = FolderManager(str(temp_dir))
        folder = manager.get_folder_for_url("https://example.com/video.mp4")
        assert "Videos" in str(folder)

    def test_set_base_path(self, temp_dir):
        manager = FolderManager()
        new_path = temp_dir / "new_folder"
        manager.set_base_path(str(new_path))
        assert manager.base_path == new_path
        assert new_path.exists()

    def test_get_all_folders(self, temp_dir):
        manager = FolderManager(str(temp_dir))
        folders = manager.get_all_folders()
        assert FileCategory.VIDEO in folders
        assert FileCategory.AUDIO in folders
        assert len(folders) == len(FileCategory)


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Event Emitter
# ══════════════════════════════════════════════════════════════════════════════


class TestEventEmitter:
    """Tests for EventEmitter class"""

    def test_event_subscription(self):
        emitter = EventEmitter()
        received = []

        def callback(data):
            received.append(data)

        unsub = emitter.on(EventType.PROGRESS, callback)
        emitter.emit(EventType.PROGRESS, {"percent": 50})

        assert len(received) == 1
        assert received[0]["percent"] == 50

        unsub()
        emitter.emit(EventType.PROGRESS, {"percent": 100})
        assert len(received) == 1

    def test_multiple_subscribers(self):
        emitter = EventEmitter()
        count = {"value": 0}

        def callback1(data):
            count["value"] += 1

        def callback2(data):
            count["value"] += 10

        emitter.on(EventType.PROGRESS, callback1)
        emitter.on(EventType.PROGRESS, callback2)
        emitter.emit(EventType.PROGRESS, {})

        assert count["value"] == 11

    def test_unsubscribe(self):
        emitter = EventEmitter()
        received = []

        def callback(data):
            received.append(data)

        emitter.on(EventType.PROGRESS, callback)
        emitter.emit(EventType.PROGRESS, {"test": 1})

        emitter.off(EventType.PROGRESS, callback)
        emitter.emit(EventType.PROGRESS, {"test": 2})

        assert len(received) == 1

    def test_off_nonexistent(self):
        emitter = EventEmitter()
        callback = Mock()
        emitter.off(EventType.PROGRESS, callback)

    def test_emit_order(self):
        emitter = EventEmitter()
        order = []

        def callback1(data):
            order.append(1)

        def callback2(data):
            order.append(2)

        emitter.on(EventType.PROGRESS, callback1)
        emitter.on(EventType.PROGRESS, callback2)
        emitter.emit(EventType.PROGRESS, {})

        assert order == [1, 2]


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Download Segment
# ══════════════════════════════════════════════════════════════════════════════


class TestDownloadSegment:
    """Tests for DownloadSegment dataclass"""

    def test_segment_creation(self):
        segment = DownloadSegment(
            segment_id=0, start_byte=0, end_byte=1023, current_byte=0
        )
        assert segment.segment_id == 0
        assert segment.start_byte == 0
        assert segment.end_byte == 1023
        assert segment.status == "pending"

    def test_is_complete_false(self):
        segment = DownloadSegment(
            segment_id=0, start_byte=0, end_byte=1023, current_byte=0
        )
        assert segment.is_complete is False

    def test_is_complete_true(self):
        segment = DownloadSegment(
            segment_id=0, start_byte=0, end_byte=1023, current_byte=1024
        )
        assert segment.is_complete is True

    def test_bytes_remaining(self):
        segment = DownloadSegment(
            segment_id=0, start_byte=0, end_byte=1023, current_byte=512
        )
        assert segment.bytes_remaining == 512


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Segment Downloader
# ══════════════════════════════════════════════════════════════════════════════


class TestSegmentDownloader:
    """Tests for SegmentDownloader class"""

    def test_creation(self):
        downloader = SegmentDownloader(num_segments=4)
        assert downloader._num_segments == 4
        assert downloader._active_workers == 0

    def test_create_segments(self):
        downloader = SegmentDownloader(num_segments=4)
        segments = downloader._create_segments(100 * 1024 * 1024)  # 100 MB

        assert len(segments) > 0
        assert segments[0].start_byte == 0
        assert segments[-1].end_byte == 100 * 1024 * 1024 - 1

        for i in range(len(segments) - 1):
            assert segments[i].end_byte + 1 == segments[i + 1].start_byte

    def test_create_segments_small_file(self):
        downloader = SegmentDownloader(num_segments=4)
        segments = downloader._create_segments(1024)  # 1 KB

        assert len(segments) == 1
        assert segments[0].start_byte == 0
        assert segments[0].end_byte == 1023

    @patch("requests.head")
    def test_get_file_size_success(self, mock_head):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Length": "1048576", "Accept-Ranges": "bytes"}
        mock_response.raise_for_status = Mock()
        mock_head.return_value = mock_response

        downloader = SegmentDownloader()
        size, supports = downloader.get_file_size("https://example.com/file.bin")

        assert size == 1048576
        assert supports is True

    @patch("requests.head")
    def test_get_file_size_no_ranges(self, mock_head):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Length": "1048576", "Accept-Ranges": "none"}
        mock_response.raise_for_status = Mock()
        mock_head.return_value = mock_response

        downloader = SegmentDownloader()
        size, supports = downloader.get_file_size("https://example.com/file.bin")

        assert size == 1048576
        assert supports is False

    @patch("requests.head")
    def test_get_file_size_error(self, mock_head):
        mock_head.side_effect = ConnectionError("Network error")

        downloader = SegmentDownloader()
        size, supports = downloader.get_file_size("https://example.com/file.bin")

        assert size is None
        assert supports is False

    def test_download_cancel(self):
        downloader = SegmentDownloader()
        downloader._cancel_event.set()

        assert downloader._cancel_event.is_set() is True

    def test_download_pause_resume(self):
        downloader = SegmentDownloader()
        downloader.pause()
        assert downloader._is_paused is True

        downloader.resume()
        assert downloader._is_paused is False


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Thread Pool
# ══════════════════════════════════════════════════════════════════════════════


class TestThreadPool:
    """Tests for ThreadPool class"""

    def test_pool_creation(self):
        pool = ThreadPool(num_workers=4)
        assert pool._num_workers == 4
        assert pool.get_active_count() == 0
        pool.shutdown(wait=True)

    def test_pool_default_workers(self):
        pool = ThreadPool()
        assert pool._num_workers == 10
        pool.shutdown(wait=True)

    def test_submit_job(self):
        pool = ThreadPool(num_workers=2)
        job = DownloadJob(
            priority=TaskPriority.NORMAL.value,
            task_id="test_job",
            url="https://example.com/file.bin",
            dest="downloads/file.bin",
            speed_limit=0,
            download_type="http",
            video_format=None,
            video_quality=None,
        )

        pool.submit(job)
        time.sleep(0.3)

        assert "test_job" in pool._task_results
        pool.shutdown(wait=True)

    def test_get_status(self):
        pool = ThreadPool(num_workers=2)
        job = DownloadJob(
            priority=1,
            task_id="status_test",
            url="https://example.com",
            dest="test.bin",
            speed_limit=0,
            download_type="http",
            video_format=None,
            video_quality=None,
        )

        pool.submit(job)
        time.sleep(0.3)

        status = pool.get_status("status_test")
        assert status is not None
        assert "status" in status

        pool.shutdown(wait=True)

    def test_cancel_task(self):
        pool = ThreadPool(num_workers=2)
        job = DownloadJob(
            priority=1,
            task_id="cancel_test",
            url="https://example.com",
            dest="test.bin",
            speed_limit=0,
            download_type="http",
            video_format=None,
            video_quality=None,
        )

        pool.submit(job)
        time.sleep(0.1)

        result = pool.cancel_task("cancel_test")
        assert result is True

        pool.shutdown(wait=True)

    def test_cancel_nonexistent(self):
        pool = ThreadPool(num_workers=2)
        result = pool.cancel_task("nonexistent")
        assert result is False
        pool.shutdown(wait=True)

    def test_get_queue_size(self):
        pool = ThreadPool(num_workers=1)
        assert pool.get_queue_size() == 0
        pool.shutdown(wait=True)

    def test_thread_safety(self):
        pool = ThreadPool(num_workers=4)
        results = {"counter": 0, "lock": threading.Lock()}

        def increment():
            for _ in range(100):
                with results["lock"]:
                    results["counter"] += 1

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results["counter"] == 1000
        pool.shutdown(wait=True)


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Download Scheduler
# ══════════════════════════════════════════════════════════════════════════════


class TestDownloadScheduler:
    """Tests for DownloadScheduler class"""

    def test_scheduler_creation(self):
        pool = ThreadPool(num_workers=2)
        scheduler = DownloadScheduler(pool, max_concurrent=2)

        assert scheduler._max_concurrent == 2
        assert scheduler.get_pending_count() == 0

        scheduler.shutdown()
        pool.shutdown(wait=True)

    def test_schedule_job(self):
        pool = ThreadPool(num_workers=2)
        scheduler = DownloadScheduler(pool, max_concurrent=2)

        job = DownloadJob(
            priority=TaskPriority.NORMAL.value,
            task_id="sched_test",
            url="https://example.com",
            dest="test.bin",
            speed_limit=0,
            download_type="http",
            video_format=None,
            video_quality=None,
        )

        scheduler.schedule(job)
        time.sleep(0.3)

        assert "sched_test" in scheduler._scheduled

        scheduler.shutdown()
        pool.shutdown(wait=True)

    def test_cancel(self):
        pool = ThreadPool(num_workers=2)
        scheduler = DownloadScheduler(pool, max_concurrent=2)

        job = DownloadJob(
            priority=1,
            task_id="cancel_sched",
            url="https://example.com",
            dest="test.bin",
            speed_limit=0,
            download_type="http",
            video_format=None,
            video_quality=None,
        )

        scheduler.schedule(job)
        time.sleep(0.1)

        result = scheduler.cancel("cancel_sched")
        assert result is True

        scheduler.shutdown()
        pool.shutdown(wait=True)


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Download Job
# ══════════════════════════════════════════════════════════════════════════════


class TestDownloadJob:
    """Tests for DownloadJob dataclass"""

    def test_job_creation(self):
        job = DownloadJob(
            priority=TaskPriority.HIGH.value,
            task_id="job123",
            url="https://example.com/file.bin",
            dest="downloads/file.bin",
            speed_limit=1024,
            download_type="http",
            video_format="mp4",
            video_quality="1080",
        )

        assert job.task_id == "job123"
        assert job.url == "https://example.com/file.bin"
        assert job.priority == 0  # HIGH = 0
        assert job.speed_limit == 1024

    def test_job_priority_ordering(self):
        high = DownloadJob(
            priority=TaskPriority.HIGH.value,
            task_id="h",
            url="",
            dest="",
            speed_limit=0,
            download_type="",
            video_format=None,
            video_quality=None,
        )
        normal = DownloadJob(
            priority=TaskPriority.NORMAL.value,
            task_id="n",
            url="",
            dest="",
            speed_limit=0,
            download_type="",
            video_format=None,
            video_quality=None,
        )
        low = DownloadJob(
            priority=TaskPriority.LOW.value,
            task_id="l",
            url="",
            dest="",
            speed_limit=0,
            download_type="",
            video_format=None,
            video_quality=None,
        )

        jobs = [low, high, normal]
        jobs.sort()

        assert jobs[0].task_id == "h"
        assert jobs[1].task_id == "n"
        assert jobs[2].task_id == "l"


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Download Task Model
# ══════════════════════════════════════════════════════════════════════════════


class TestDownloadTask:
    """Tests for DownloadTask model"""

    def test_task_creation_default(self):
        task = DownloadTask(
            id="task1",
            url="https://example.com/file.bin",
            dest_path=Path("/tmp/file.bin"),
        )

        assert task.id == "task1"
        assert task.status == Status.PENDING
        assert task.bytes_downloaded == 0
        assert task.total_bytes == 0

    def test_task_with_video(self):
        task = DownloadTask(
            id="task2",
            url="https://youtube.com/watch?v=abc",
            dest_path=Path("/tmp/video.mp4"),
            download_type=DownloadType.VIDEO,
            video_format=VideoFormat.MP4,
            video_quality=VideoQuality.QUALITY_1080,
            title="Test Video",
        )

        assert task.download_type == DownloadType.VIDEO
        assert task.video_format == VideoFormat.MP4
        assert task.video_quality == VideoQuality.QUALITY_1080
        assert task.title == "Test Video"

    def test_task_status_transitions(self):
        task = DownloadTask(
            id="task3",
            url="https://example.com/file.bin",
            dest_path=Path("/tmp/file.bin"),
        )

        assert task.status == Status.PENDING

        task.status = Status.DOWNLOADING
        assert task.status == Status.DOWNLOADING

        task.status = Status.COMPLETED
        assert task.status == Status.COMPLETED

    def test_task_progress(self):
        task = DownloadTask(
            id="task4",
            url="https://example.com/file.bin",
            dest_path=Path("/tmp/file.bin"),
            total_bytes=1000,
        )

        task.bytes_downloaded = 500
        assert task.bytes_downloaded == 500
        assert task.total_bytes == 1000


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Video Format & Quality
# ══════════════════════════════════════════════════════════════════════════════


class TestVideoEnums:
    """Tests for VideoFormat and VideoQuality enums"""

    def test_video_formats(self):
        assert VideoFormat.BEST.value == "best"
        assert VideoFormat.MP4.value == "mp4"
        assert VideoFormat.WEBM.value == "webm"
        assert VideoFormat.MP3.value == "mp3"
        assert VideoFormat.WAV.value == "wav"
        assert VideoFormat.FLAC.value == "flac"

    def test_video_qualities(self):
        assert VideoQuality.BEST.value == "best"
        assert VideoQuality.QUALITY_4K.value == "2160"
        assert VideoQuality.QUALITY_1080.value == "1080"
        assert VideoQuality.QUALITY_720.value == "720"
        assert VideoQuality.QUALITY_480.value == "480"


# ══════════════════════════════════════════════════════════════════════════════
# TEST: File Category
# ══════════════════════════════════════════════════════════════════════════════


class TestFileCategory:
    """Tests for FileCategory enum"""

    def test_categories(self):
        assert FileCategory.VIDEO.value == "video"
        assert FileCategory.AUDIO.value == "audio"
        assert FileCategory.IMAGE.value == "image"
        assert FileCategory.DOCUMENT.value == "document"
        assert FileCategory.ARCHIVE.value == "archive"
        assert FileCategory.APPLICATION.value == "application"
        assert FileCategory.OTHER.value == "other"


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Status Enum
# ══════════════════════════════════════════════════════════════════════════════


class TestStatus:
    """Tests for Status enum"""

    def test_statuses(self):
        assert Status.PENDING.value == "pending"
        assert Status.DOWNLOADING.value == "downloading"
        assert Status.PAUSED.value == "paused"
        assert Status.COMPLETED.value == "completed"
        assert Status.CANCELLED.value == "cancelled"
        assert Status.ERROR.value == "error"
        assert Status.EXTRACTING.value == "extracting"


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Download Type
# ══════════════════════════════════════════════════════════════════════════════


class TestDownloadType:
    """Tests for DownloadType enum"""

    def test_types(self):
        assert DownloadType.HTTP.value == "http"
        assert DownloadType.VIDEO.value == "video"


# ══════════════════════════════════════════════════════════════════════════════
# TEST: Integration Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests for multiple components"""

    def test_url_parser_to_file_handler(self):
        url = "https://example.com/video.mp4"

        assert URLParser.is_supported_video(url) is False

        category, ext, folder = FileTypeDetector.detect_from_url(url)
        assert category == FileCategory.VIDEO
        assert ext == ".mp4"
        assert folder == "Videos"

    def test_video_url_flow(self):
        url = "https://youtube.com/watch?v=abc123"

        assert URLParser.is_supported_video(url) is True
        assert URLParser.get_platform_name(url) == "YouTube"
        assert URLParser.get_download_type(url) == DownloadType.VIDEO

    def test_task_to_segment(self):
        task = DownloadTask(
            id="int_test",
            url="https://example.com/large.bin",
            dest_path=Path("/tmp/large.bin"),
            total_bytes=100 * 1024 * 1024,  # 100 MB
        )

        downloader = SegmentDownloader(num_segments=4)
        segments = downloader._create_segments(task.total_bytes)

        assert len(segments) == 4
        assert sum(s.end_byte - s.start_byte + 1 for s in segments) == task.total_bytes

    def test_event_flow(self):
        emitter = EventEmitter()
        results = []

        def on_progress(data):
            results.append(("progress", data))

        def on_complete(data):
            results.append(("complete", data))

        emitter.on(EventType.PROGRESS, on_progress)
        emitter.on(EventType.COMPLETED, on_complete)

        emitter.emit(EventType.PROGRESS, {"percent": 50})
        emitter.emit(EventType.PROGRESS, {"percent": 100})
        emitter.emit(EventType.COMPLETED, {"path": "/tmp/file.bin"})

        assert len(results) == 3
        assert results[0] == ("progress", {"percent": 50})
        assert results[-1] == ("complete", {"path": "/tmp/file.bin"})


# ══════════════════════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
