import requests
import threading
import os
import time
from typing import Optional, Callable, Dict, List, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue

from .logger import get_logger, ErrorHandler, Logger


@dataclass
class DownloadSegment:
    segment_id: int
    start_byte: int
    end_byte: int
    current_byte: int = 0
    status: str = "pending"
    data: bytes = field(default_factory=bytes)
    error: Optional[str] = None
    
    @property
    def is_complete(self) -> bool:
        return self.current_byte >= self.end_byte - self.start_byte + 1
    
    @property
    def bytes_remaining(self) -> int:
        return max(0, (self.end_byte - self.start_byte + 1) - self.current_byte)


class SegmentDownloader:
    MIN_SEGMENT_SIZE = 5 * 1024 * 1024
    MIN_FILE_SIZE_FOR_SEGMENTATION = 100 * 1024 * 1024
    DEFAULT_NUM_SEGMENTS = 8
    CHUNK_SIZE = 64 * 1024
    
    def __init__(self, num_segments: int = DEFAULT_NUM_SEGMENTS, logger: Optional[Logger] = None):
        self._num_segments = num_segments
        self._segments: List[DownloadSegment] = []
        self._segment_locks: Dict[int, threading.Lock] = {}
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._is_paused = False
        self._total_bytes = 0
        self._downloaded_bytes = 0
        self._progress_lock = threading.Lock()
        self._active_workers = 0
        self._active_lock = threading.Lock()
        self._logger = logger or get_logger()
        self._error_handler = ErrorHandler(self._logger)
    
    def get_file_size(self, url: str, headers: Optional[dict] = None) -> Tuple[Optional[int], bool]:
        try:
            self._logger.debug(f"Определение размера файла: {url}")
            
            resp = requests.head(url, headers=headers, timeout=30, allow_redirects=True)
            resp.raise_for_status()
            
            content_length = resp.headers.get("Content-Length")
            accept_ranges = resp.headers.get("Accept-Ranges", "none").lower()
            
            supports_ranges = accept_ranges == "bytes" or "bytes" in accept_ranges
            
            if content_length:
                total_size = int(content_length)
                self._logger.debug(f"Размер файла: {total_size} bytes, Range: {supports_ranges}")
                return total_size, supports_ranges
            
            resp = requests.get(url, headers=headers, stream=True, timeout=30)
            resp.raise_for_status()
            
            content_length = resp.headers.get("Content-Length")
            if content_length:
                total_size = int(content_length)
                accept_ranges = resp.headers.get("Accept-Ranges", "none").lower()
                supports_ranges = accept_ranges == "bytes" or "bytes" in accept_ranges
                return total_size, supports_ranges
            
            return None, False
            
        except Exception as e:
            error_info = self._error_handler.handle(e, f"HEAD {url}")
            return None, False
    
    def _create_segments(self, total_size: int) -> List[DownloadSegment]:
        segment_size = max(total_size // self._num_segments, self.MIN_SEGMENT_SIZE)
        
        if segment_size < self.MIN_SEGMENT_SIZE:
            segment_size = self.MIN_SEGMENT_SIZE
        
        segments = []
        current_pos = 0
        
        for i in range(self._num_segments):
            start = current_pos
            if i == self._num_segments - 1:
                end = total_size - 1
            else:
                end = min(current_pos + segment_size - 1, total_size - 1)
            
            if start <= end:
                segment = DownloadSegment(
                    segment_id=i,
                    start_byte=start,
                    end_byte=end,
                    current_byte=0
                )
                segments.append(segment)
                self._segment_locks[i] = threading.Lock()
            
            current_pos = end + 1
            
            if current_pos >= total_size:
                break
        
        return segments
    
    def download(self, url: str, dest_path: Path,
                 progress_callback: Optional[Callable] = None,
                 speed_limit: int = 0) -> Tuple[bool, Optional[str]]:
        
        self._cancel_event.clear()
        self._pause_event.clear()
        self._is_paused = False
        
        self._logger.info(f"Начало загрузки: {url}")
        
        total_size, supports_ranges = self.get_file_size(url)
        
        if total_size is None:
            error_info = self._error_handler.handle(
                ConnectionError("Не удалось определить размер файла"),
                f"HEAD {url}"
            )
            return False, error_info["message"]
        
        self._total_bytes = total_size
        
        use_segmentation = (total_size >= self.MIN_FILE_SIZE_FOR_SEGMENTATION 
                           and supports_ranges 
                           and self._num_segments > 1)
        
        self._logger.info(f"Размер: {total_size / (1024*1024):.1f} MB, "
                         f"Сегментация: {'Да' if use_segmentation else 'Нет'}")
        
        part_file = dest_path.with_suffix(dest_path.suffix + ".part")
        
        if use_segmentation:
            return self._download_segmented(url, dest_path, part_file, total_size, progress_callback, speed_limit)
        else:
            return self._download_single(url, dest_path, progress_callback, speed_limit)
    
    def _download_single(self, url: str, dest_path: Path,
                        progress_callback: Optional[Callable],
                        speed_limit: int) -> Tuple[bool, Optional[str]]:
        try:
            self._logger.debug(f"Обычная загрузка: {url}")
            
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            
            self._total_bytes = int(resp.headers.get("Content-Length", 0))
            self._downloaded_bytes = 0
            
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=self.CHUNK_SIZE):
                    if self._cancel_event.is_set():
                        self._logger.info("Загрузка отменена пользователем")
                        return False, "Загрузка отменена"
                    
                    while self._is_paused:
                        self._pause_event.wait()
                        if self._cancel_event.is_set():
                            self._logger.info("Загрузка отменена пользователем")
                            return False, "Загрузка отменена"
                    
                    if chunk:
                        if speed_limit > 0:
                            self._apply_rate_limit(len(chunk), speed_limit)
                        
                        try:
                            f.write(chunk)
                        except OSError as e:
                            error_info = self._error_handler.handle(e, "Запись в файл")
                            return False, error_info["message"]
                        
                        with self._progress_lock:
                            self._downloaded_bytes += len(chunk)
                        
                        if progress_callback:
                            progress_callback({
                                "downloaded": self._downloaded_bytes,
                                "total": self._total_bytes,
                                "percent": (self._downloaded_bytes / self._total_bytes * 100) if self._total_bytes > 0 else 0
                            })
            
            self._logger.info(f"Загрузка завершена: {dest_path}")
            return True, None
            
        except Exception as e:
            error_info = self._error_handler.handle(e, f"Загрузка {url}")
            return False, error_info["message"]
    
    def _download_segmented(self, url: str, dest_path: Path, part_file: Path,
                           total_size: int,
                           progress_callback: Optional[Callable],
                           speed_limit: int) -> Tuple[bool, Optional[str]]:
        
        self._segments = self._create_segments(total_size)
        self._downloaded_bytes = 0
        
        for seg in self._segments:
            seg.data = b""
            seg.current_byte = 0
            seg.status = "pending"
        
        existing_size = 0
        if part_file.exists():
            existing_size = part_file.stat().st_size
            for seg in self._segments:
                if seg.start_byte < existing_size:
                    seg.current_byte = seg.end_byte - seg.start_byte + 1
                    seg.status = "completed"
                    existing_size = min(existing_size, seg.end_byte + 1)
        
        for seg in self._segments:
            if seg.status != "completed":
                resume_pos = existing_size - seg.start_byte if existing_size > seg.start_byte else 0
                seg.current_byte = resume_pos
                seg.status = "pending"
        
        self._download_segment_bytes(url, progress_callback, speed_limit)
        
        if self._cancel_event.is_set():
            return False, "Загрузка отменена"
        
        return self._merge_segments(dest_path, part_file)
    
    def _download_segment_bytes(self, url: str,
                                 progress_callback: Optional[Callable],
                                 speed_limit: int):
        
        incomplete_segments = [s for s in self._segments if s.status != "completed"]
        
        if not incomplete_segments:
            return
        
        remaining_per_segment = [(s, s.bytes_remaining) for s in incomplete_segments]
        remaining_per_segment.sort(key=lambda x: x[1], reverse=True)
        
        for seg, _ in remaining_per_segment:
            seg.status = "downloading"
        
        threads: List[threading.Thread] = []
        
        for seg in incomplete_segments[:self._num_segments]:
            thread = threading.Thread(
                target=self._download_single_segment,
                args=(url, seg, progress_callback, speed_limit),
                daemon=True
            )
            thread.start()
            threads.append(thread)
            
            with self._active_lock:
                self._active_workers += 1
        
        for thread in threads:
            thread.join()
    
    def _download_single_segment(self, url: str, segment: DownloadSegment,
                                progress_callback: Optional[Callable],
                                speed_limit: int):
        try:
            headers = {
                "Range": f"bytes={segment.start_byte + segment.current_byte}-{segment.end_byte}"
            }
            
            resp = requests.get(url, headers=headers, stream=True, timeout=60)
            resp.raise_for_status()
            
            local_data = bytearray()
            
            for chunk in resp.iter_content(chunk_size=self.CHUNK_SIZE):
                if self._cancel_event.is_set():
                    segment.status = "cancelled"
                    return
                
                while self._is_paused:
                    self._pause_event.wait()
                    if self._cancel_event.is_set():
                        segment.status = "cancelled"
                        return
                
                if chunk:
                    if speed_limit > 0:
                        self._apply_rate_limit(len(chunk), speed_limit)
                    
                    local_data.extend(chunk)
                    
                    with self._segment_locks.get(segment.segment_id, threading.Lock()):
                        segment.current_byte += len(chunk)
                        segment.data = bytes(local_data)
                    
                    with self._progress_lock:
                        self._downloaded_bytes = sum(s.current_byte for s in self._segments)
                    
                    if progress_callback:
                        progress_callback({
                            "downloaded": self._downloaded_bytes,
                            "total": self._total_bytes,
                            "percent": (self._downloaded_bytes / self._total_bytes * 100) if self._total_bytes > 0 else 0,
                            "segments": [s.current_byte for s in self._segments]
                        })
            
            segment.status = "completed"
            
        except Exception as e:
            segment.status = "error"
            segment.error = str(e)
        finally:
            with self._active_lock:
                self._active_workers -= 1
    
    def _merge_segments(self, dest_path: Path, part_file: Path) -> Tuple[bool, Optional[str]]:
        try:
            incomplete = [s for s in self._segments if s.status != "completed"]
            if incomplete:
                errors = [f"Segment {s.segment_id}: {s.error}" for s in incomplete if s.error]
                return False, f"Не все сегменты загружены: {'; '.join(errors[:3])}"
            
            self._segments.sort(key=lambda s: s.start_byte)
            
            with open(part_file, "wb") as f:
                for segment in self._segments:
                    f.write(segment.data)
                    segment.data = b""
            
            if dest_path.exists():
                dest_path.unlink()
            part_file.rename(dest_path)
            
            return True, None
            
        except Exception as e:
            return False, f"Ошибка объединения: {str(e)}"
    
    def pause(self):
        self._is_paused = True
        self._pause_event.clear()
    
    def resume(self):
        self._is_paused = False
        self._pause_event.set()
    
    def cancel(self):
        self._cancel_event.set()
        self._pause_event.set()
    
    def _apply_rate_limit(self, bytes_written: int, limit: int):
        max_time = bytes_written / limit
        check_interval = 0.05
        elapsed = 0
        
        while elapsed < max_time:
            if self._cancel_event.is_set():
                break
            time.sleep(min(check_interval, max_time - elapsed))
            elapsed += check_interval


class SegmentedDownloadManager:
    def __init__(self, max_concurrent: int = 10, num_segments: int = 8):
        self._max_concurrent = max_concurrent
        self._num_segments = num_segments
        self._tasks: Dict[str, dict] = {}
        self._downloaders: Dict[str, SegmentDownloader] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._pause_events: Dict[str, threading.Event] = {}
        self._manager_lock = threading.Lock()
        self._default_path = Path.home() / "Downloads"
    
    def add_download(self, url: str, dest: Optional[str] = None,
                     speed_limit: int = 0) -> str:
        
        task_id = f"seg_{int(time.time() * 1000)}"
        
        dest_path = Path(dest) if dest else self._default_path / self._extract_filename(url)
        
        with self._manager_lock:
            self._tasks[task_id] = {
                "url": url,
                "dest": dest_path,
                "status": "pending",
                "progress": 0.0,
                "downloaded": 0,
                "total": 0,
                "speed_limit": speed_limit,
                "num_segments": self._num_segments,
                "segments_completed": 0
            }
            self._cancel_events[task_id] = threading.Event()
            self._pause_events[task_id] = threading.Event()
            self._locks[task_id] = threading.Lock()
        
        thread = threading.Thread(
            target=self._download_worker,
            args=(task_id,),
            daemon=True
        )
        thread.start()
        
        return task_id
    
    def _download_worker(self, task_id: str):
        task = self._tasks.get(task_id)
        if not task:
            return
        
        task["status"] = "downloading"
        
        def progress_callback(data):
            with self._manager_lock:
                if task_id in self._tasks:
                    self._tasks[task_id]["progress"] = data.get("percent", 0)
                    self._tasks[task_id]["downloaded"] = data.get("downloaded", 0)
                    self._tasks[task_id]["total"] = data.get("total", 0)
                    
                    if "segments" in data:
                        self._tasks[task_id]["segments_completed"] = sum(1 for s in self._tasks[task_id].get("segments", []) if s > 0)
        
        downloader = SegmentDownloader(num_segments=self._num_segments)
        self._downloaders[task_id] = downloader
        
        success, error = downloader.download(
            url=task["url"],
            dest_path=task["dest"],
            progress_callback=progress_callback,
            speed_limit=task["speed_limit"]
        )
        
        with self._manager_lock:
            if task_id in self._tasks:
                if success:
                    self._tasks[task_id]["status"] = "completed"
                else:
                    self._tasks[task_id]["status"] = "error"
                    self._tasks[task_id]["error"] = error
        
        self._downloaders.pop(task_id, None)
    
    def pause(self, task_id: str) -> bool:
        downloader = self._downloaders.get(task_id)
        if downloader:
            downloader.pause()
            with self._manager_lock:
                if task_id in self._tasks:
                    self._tasks[task_id]["status"] = "paused"
            return True
        return False
    
    def resume(self, task_id: str) -> bool:
        downloader = self._downloaders.get(task_id)
        if downloader:
            downloader.resume()
            with self._manager_lock:
                if task_id in self._tasks:
                    self._tasks[task_id]["status"] = "downloading"
            return True
        return False
    
    def cancel(self, task_id: str) -> bool:
        downloader = self._downloaders.get(task_id)
        if downloader:
            downloader.cancel()
            with self._manager_lock:
                if task_id in self._tasks:
                    self._tasks[task_id]["status"] = "cancelled"
            return True
        return False
    
    def get_progress(self, task_id: str) -> Optional[dict]:
        with self._manager_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            return task.copy()
    
    def get_all_tasks(self) -> list:
        with self._manager_lock:
            return [{"id": tid, **task} for tid, task in self._tasks.items()]
    
    def set_default_path(self, path: str):
        self._default_path = Path(path)
    
    def _extract_filename(self, url: str) -> str:
        path = url.split("/")[-1]
        name = path.split("?")[0]
        return name if name else f"download_{int(time.time())}"
    
    def cleanup_completed(self):
        with self._manager_lock:
            completed = [tid for tid, t in self._tasks.items() 
                        if t["status"] in ("completed", "cancelled", "error")]
            for tid in completed:
                self._tasks.pop(tid, None)
                self._cancel_events.pop(tid, None)
                self._pause_events.pop(tid, None)
                self._locks.pop(tid, None)
