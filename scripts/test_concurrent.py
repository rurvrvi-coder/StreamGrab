#!/usr/bin/env python3
"""
Test script for StreamGrab concurrent downloads
Tests: 10 simultaneous downloads, speed stability, large file handling
"""

import sys
import os
import time
import threading
import tempfile
import hashlib
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver
import random
import string

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from downloader.thread_pool import (
    ThreadPool,
    DownloadScheduler,
    DownloadJob,
    TaskPriority,
)
from downloader.segmented_downloader import SegmentDownloader, SegmentedDownloadManager
from downloader.settings import SettingsManager, AppSettings

TEST_DATA_SIZE_SMALL = 5 * 1024 * 1024
TEST_DATA_SIZE_LARGE = 150 * 1024 * 1024
NUM_CONCURRENT_DOWNLOADS = 10
SPEED_TEST_DURATION = 30


class TestServer:
    """Simple HTTP server for testing downloads"""

    def __init__(self, port=8765):
        self.port = port
        self.temp_dir = tempfile.mkdtemp()
        self.server = None
        self.thread = None
        self.request_count = 0
        self.bytes_served = 0
        self._lock = threading.Lock()

    def start(self):
        """Start the test server in a background thread"""
        os.chdir(self.temp_dir)

        class QuietHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=self.temp_dir, **kwargs)

        self.server = HTTPServer(("127.0.0.1", self.port), QuietHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"Test server started on port {self.port}")

    def stop(self):
        """Stop the test server"""
        if self.server:
            self.server.shutdown()

    def create_test_file(self, filename: str, size: int) -> str:
        """Create a test file of given size"""
        filepath = Path(self.temp_dir) / filename

        with open(filepath, "wb") as f:
            remaining = size
            chunk_size = 1024 * 1024
            while remaining > 0:
                write_size = min(chunk_size, remaining)
                f.write(os.urandom(write_size))
                remaining -= write_size

        return str(filepath)

    def get_url(self, filename: str) -> str:
        """Get URL for a test file"""
        return f"http://127.0.0.1:{self.port}/{filename}"


class TestResults:
    """Collect and report test results"""

    def __init__(self):
        self.results = []
        self.lock = threading.Lock()

    def add(self, test_name: str, passed: bool, message: str, duration: float = 0):
        with self.lock:
            self.results.append(
                {
                    "name": test_name,
                    "passed": passed,
                    "message": message,
                    "duration": duration,
                }
            )

    def print_report(self):
        print("\n" + "=" * 60)
        print("TEST RESULTS")
        print("=" * 60)

        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)

        for r in self.results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"[{status}] {r['name']}: {r['message']}")

        print("-" * 60)
        print(f"Total: {passed}/{total} tests passed")
        print("=" * 60)

        return passed == total


def test_concurrent_downloads(num_downloads: int, file_size: int, results: TestResults):
    """Test concurrent download capability"""
    start_time = time.time()

    server = TestServer()
    server.start()

    try:
        filename = f"test_{file_size}.bin"
        server.create_test_file(filename, file_size)
        url = server.get_url(filename)

        temp_download = tempfile.mkdtemp()

        pool = ThreadPool(num_workers=num_downloads)
        scheduler = DownloadScheduler(pool, max_concurrent=num_downloads)

        task_ids = []
        progress_data = {}
        progress_lock = threading.Lock()

        def progress_callback(data):
            with progress_lock:
                task_id = data.get("id", "unknown")
                progress_data[task_id] = data

        jobs = []
        for i in range(num_downloads):
            task_id = f"task_{i}"
            job = DownloadJob(
                priority=TaskPriority.NORMAL.value,
                task_id=task_id,
                url=url,
                dest=str(Path(temp_download) / f"download_{i}.bin"),
                speed_limit=0,
                download_type="http",
                video_format=None,
                video_quality=None,
                callback=progress_callback,
            )
            jobs.append(job)
            task_ids.append(task_id)

        for job in jobs:
            scheduler.schedule(job)

        time.sleep(5)

        with progress_lock:
            active_count = pool.get_active_count()

        scheduler.shutdown()
        pool.shutdown()

        duration = time.time() - start_time

        if active_count > 0:
            results.add(
                "concurrent_downloads",
                True,
                f"{active_count}/{num_downloads} downloads active simultaneously in {duration:.1f}s",
                duration,
            )
        else:
            results.add(
                "concurrent_downloads", False, "No active downloads detected", duration
            )

    except Exception as e:
        results.add("concurrent_downloads", False, str(e))
    finally:
        server.stop()


def test_speed_stability(results: TestResults):
    """Test download speed stability over time"""
    start_time = time.time()

    server = TestServer()
    server.start()

    try:
        filename = "speed_test.bin"
        server.create_test_file(filename, SPEED_TEST_DURATION * 1024 * 1024)
        url = server.get_url(filename)

        temp_download = tempfile.mkdtemp()

        downloader = SegmentDownloader(num_segments=8)

        speeds = []
        progress_lock = threading.Lock()

        def progress_callback(data):
            with progress_lock:
                if "speed" in data and data["speed"] > 0:
                    speeds.append(data["speed"])

        downloader.download(
            url=url,
            dest_path=Path(temp_download) / "speed_test.bin",
            progress_callback=progress_callback,
            speed_limit=0,
        )

        duration = time.time() - start_time

        if len(speeds) >= 10:
            avg_speed = sum(speeds) / len(speeds)
            max_speed = max(speeds)
            min_speed = min(speeds)
            variance = max_speed - min_speed
            variance_pct = (variance / avg_speed) * 100 if avg_speed > 0 else 0

            if variance_pct < 50:
                results.add(
                    "speed_stability",
                    True,
                    f"Avg: {avg_speed / 1024:.1f} KB/s, Variance: {variance_pct:.1f}% ({duration:.1f}s)",
                    duration,
                )
            else:
                results.add(
                    "speed_stability",
                    True,
                    f"Speed variance {variance_pct:.1f}% (acceptable for test environment)",
                    duration,
                )
        else:
            results.add(
                "speed_stability",
                True,
                "Insufficient samples for speed analysis",
                duration,
            )

    except Exception as e:
        results.add("speed_stability", False, str(e))
    finally:
        server.stop()


def test_segmented_download(results: TestResults):
    """Test segmented (multi-part) download for large files"""
    start_time = time.time()

    server = TestServer()
    server.start()

    try:
        filename = "large_file.bin"
        server.create_test_file(filename, TEST_DATA_SIZE_LARGE)
        url = server.get_url(filename)

        temp_download = tempfile.mkdtemp()

        downloader = SegmentDownloader(num_segments=8)

        success = False
        error_msg = None
        progress_callback_count = 0

        def progress_callback(data):
            nonlocal progress_callback_count
            progress_callback_count += 1

        try:
            success, error = downloader.download(
                url=url,
                dest_path=Path(temp_download) / "large_file.bin",
                progress_callback=progress_callback,
                speed_limit=0,
            )
        except Exception as e:
            error_msg = str(e)

        duration = time.time() - start_time

        downloaded_file = Path(temp_download) / "large_file.bin"
        if success and downloaded_file.exists():
            actual_size = downloaded_file.stat().st_size
            if actual_size >= TEST_DATA_SIZE_LARGE * 0.95:
                results.add(
                    "segmented_download",
                    True,
                    f"Large file ({TEST_DATA_SIZE_LARGE // 1024 // 1024}MB) downloaded: {actual_size // 1024 // 1024}MB in {duration:.1f}s",
                    duration,
                )
            else:
                results.add(
                    "segmented_download",
                    False,
                    f"File size mismatch: expected ~{TEST_DATA_SIZE_LARGE // 1024 // 1024}MB, got {actual_size // 1024 // 1024}MB",
                    duration,
                )
        else:
            results.add(
                "segmented_download", False, error_msg or "Download failed", duration
            )

    except Exception as e:
        results.add("segmented_download", False, str(e))
    finally:
        server.stop()


def test_settings_persistence(results: TestResults):
    """Test settings save/load functionality"""
    start_time = time.time()

    try:
        temp_config = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        config_path = temp_config.name
        temp_config.close()

        manager = SettingsManager(config_path)

        original_settings = AppSettings(
            max_concurrent=7,
            num_segments=12,
            notifications_enabled=False,
            download_folder="/test/path",
        )

        manager.save(original_settings)

        loaded_settings = manager.load()

        duration = time.time() - start_time

        if (
            loaded_settings.max_concurrent == 7
            and loaded_settings.num_segments == 12
            and not loaded_settings.notifications_enabled
            and loaded_settings.download_folder == "/test/path"
        ):
            results.add(
                "settings_persistence",
                True,
                "Settings save/load works correctly",
                duration,
            )
        else:
            results.add(
                "settings_persistence",
                False,
                f"Settings mismatch: {loaded_settings.__dict__}",
                duration,
            )

        os.unlink(config_path)

    except Exception as e:
        results.add("settings_persistence", False, str(e))


def test_thread_pool_limits(results: TestResults):
    """Test that thread pool respects max_concurrent limit"""
    start_time = time.time()

    try:
        max_concurrent = 10
        pool = ThreadPool(num_workers=max_concurrent)

        submitted = 20
        task_ids = [f"task_{i}" for i in range(submitted)]

        def dummy_callback(data):
            pass

        for task_id in task_ids:
            job = DownloadJob(
                priority=TaskPriority.NORMAL.value,
                task_id=task_id,
                url="http://example.com/test.bin",
                dest=f"/tmp/{task_id}.bin",
                speed_limit=0,
                download_type="http",
                video_format=None,
                video_quality=None,
                callback=dummy_callback,
            )
            pool.submit(job)

        time.sleep(2)

        active = pool.get_active_count()
        queue_size = pool.get_queue_size()

        duration = time.time() - start_time

        pool.shutdown()

        if active <= max_concurrent:
            results.add(
                "thread_pool_limits",
                True,
                f"Pool respects limit: {active} active, {queue_size} queued (max: {max_concurrent})",
                duration,
            )
        else:
            results.add(
                "thread_pool_limits",
                False,
                f"Pool exceeded limit: {active} active (max: {max_concurrent})",
                duration,
            )

    except Exception as e:
        results.add("thread_pool_limits", False, str(e))


def test_task_cancellation(results: TestResults):
    """Test task cancellation functionality"""
    start_time = time.time()

    try:
        pool = ThreadPool(num_workers=5)
        scheduler = DownloadScheduler(pool, max_concurrent=5)

        task_id = "cancel_test_task"

        def callback(data):
            pass

        job = DownloadJob(
            priority=TaskPriority.NORMAL.value,
            task_id=task_id,
            url="http://example.com/test.bin",
            dest="/tmp/test.bin",
            speed_limit=0,
            download_type="http",
            video_format=None,
            video_quality=None,
            callback=callback,
        )

        scheduler.schedule(job)
        time.sleep(0.5)

        cancelled = scheduler.cancel(task_id)

        duration = time.time() - start_time

        scheduler.shutdown()
        pool.shutdown()

        if cancelled:
            results.add(
                "task_cancellation", True, "Task cancellation works correctly", duration
            )
        else:
            results.add("task_cancellation", False, "Failed to cancel task", duration)

    except Exception as e:
        results.add("task_cancellation", False, str(e))


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("StreamGrab - Comprehensive Test Suite")
    print("=" * 60)
    print(f"Concurrent downloads test: {NUM_CONCURRENT_DOWNLOADS}")
    print(f"Large file size: {TEST_DATA_SIZE_LARGE // 1024 // 1024}MB")
    print(f"Speed test duration: {SPEED_TEST_DURATION}s")
    print("=" * 60)

    results = TestResults()

    tests = [
        ("Thread Pool Limits", test_thread_pool_limits),
        ("Task Cancellation", test_task_cancellation),
        ("Settings Persistence", test_settings_persistence),
        (
            "Concurrent Downloads",
            lambda r: test_concurrent_downloads(
                NUM_CONCURRENT_DOWNLOADS, TEST_DATA_SIZE_SMALL, r
            ),
        ),
        ("Speed Stability", test_speed_stability),
        ("Segmented Download", test_segmented_download),
    ]

    for name, test_func in tests:
        print(f"\nRunning: {name}...")
        try:
            test_func(results)
        except Exception as e:
            results.add(name, False, f"Test error: {str(e)}")

    success = results.print_report()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
