import requests
from threading import Thread, Lock, Event, Semaphore
from pathlib import Path
from typing import Dict, Optional
import time
import uuid

from .models import DownloadTask, Status, DownloadType, VideoFormat, VideoQuality
from .events import EventEmitter, EventType
from .url_parser import URLParser
from .ytdlp_downloader import YTDLPDownloader, VideoInfoExtractor


class DownloadManager:
    _instance = None

    def __new__(cls, max_concurrent: int = 10):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_concurrent: int = 10):
        if self._initialized:
            return
        self._initialized = True

        self._tasks: Dict[str, DownloadTask] = {}
        self._threads: Dict[str, Thread] = {}
        self._pause_events: Dict[str, Event] = {}
        self._cancel_events: Dict[str, Event] = {}
        self._locks: Dict[str, Lock] = {}
        self._resume_positions: Dict[str, int] = {}
        self._manager_lock = Lock()
        self._events = EventEmitter()
        self._max_concurrent = max_concurrent
        self._active_semaphore = Semaphore(max_concurrent)
        self._default_save_path = Path.cwd() / "downloads"
        self._default_save_path.mkdir(exist_ok=True)

        self._max_speed: int = 0

    @property
    def events(self) -> EventEmitter:
        return self._events

    def add_download(self, url: str, dest: Optional[str] = None, 
                     speed_limit: int = 0) -> str:
        download_type = URLParser.get_download_type(url)
        
        if download_type == DownloadType.VIDEO:
            return self.add_video_download(url, dest, speed_limit)
        else:
            return self._add_http_download(url, dest, speed_limit)

    def add_video_download(self, url: str, dest: Optional[str] = None,
                           speed_limit: int = 0,
                           video_format: Optional[VideoFormat] = None,
                           video_quality: Optional[VideoQuality] = None) -> str:
        
        if not URLParser.is_supported_video(url):
            raise ValueError(f"URL не поддерживается: {url}")
        
        if not URLParser.is_valid_url(url):
            raise ValueError(f"Некорректный URL: {url}")
        
        task_id = str(uuid.uuid4())[:8]
        dest_path = Path(dest) if dest else self._default_save_path
        
        task = DownloadTask(
            id=task_id,
            url=url,
            dest_path=dest_path,
            status=Status.EXTRACTING,
            speed_limit=speed_limit,
            created_at=time.time(),
            download_type=DownloadType.VIDEO,
            video_format=video_format,
            video_quality=video_quality,
        )

        with self._manager_lock:
            self._tasks[task_id] = task
            self._pause_events[task_id] = Event()
            self._cancel_events[task_id] = Event()
            self._locks[task_id] = Lock()

        thread = Thread(target=self._video_download_worker, args=(task_id,), daemon=True)
        self._threads[task_id] = thread
        thread.start()

        self._events.emit(EventType.ADDED, {
            "id": task_id, 
            "url": url,
            "type": "video"
        })
        return task_id

    def _add_http_download(self, url: str, dest: Optional[str] = None, 
                          speed_limit: int = 0) -> str:
        task_id = str(uuid.uuid4())[:8]
        filename = self._extract_filename(url)
        dest_path = Path(dest) if dest else self._default_save_path / filename  # type: ignore

        task = DownloadTask(
            id=task_id,
            url=url,
            dest_path=dest_path,
            status=Status.PENDING,
            speed_limit=speed_limit,
            created_at=time.time(),
            download_type=DownloadType.HTTP,
        )

        with self._manager_lock:
            self._tasks[task_id] = task
            self._pause_events[task_id] = Event()
            self._cancel_events[task_id] = Event()
            self._locks[task_id] = Lock()

        thread = Thread(target=self._http_download_worker, args=(task_id,), daemon=True)
        self._threads[task_id] = thread
        thread.start()

        self._events.emit(EventType.ADDED, {"id": task_id, "url": url, "type": "http"})
        return task_id

    def get_video_info(self, url: str):
        return VideoInfoExtractor.get_video_info(url)

    def get_available_formats(self, url: str):
        return VideoInfoExtractor.get_available_formats(url)

    def is_video_url(self, url: str) -> bool:
        return URLParser.is_supported_video(url)

    def get_platform_name(self, url: str) -> Optional[str]:
        return URLParser.get_platform_name(url)

    def pause(self, task_id: str) -> bool:
        if task_id not in self._pause_events:
            return False
        self._pause_events[task_id].set()
        task = self._tasks.get(task_id)
        if task:
            task.status = Status.PAUSED
        self._events.emit(EventType.PAUSED, {"id": task_id})
        return True

    def resume(self, task_id: str) -> bool:
        if task_id not in self._pause_events:
            return False
        self._pause_events[task_id].clear()
        task = self._tasks.get(task_id)
        if task:
            task.status = Status.DOWNLOADING
        self._events.emit(EventType.RESUMED, {"id": task_id})
        return True

    def cancel(self, task_id: str) -> bool:
        if task_id not in self._cancel_events:
            return False
        self._cancel_events[task_id].set()
        
        with self._manager_lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = Status.CANCELLED
                if task.download_type == DownloadType.HTTP:
                    part_file = Path(str(task.dest_path) + ".part")
                    if part_file.exists():
                        try:
                            part_file.unlink()
                        except Exception:
                            pass

        self._events.emit(EventType.CANCELLED, {"id": task_id})
        return True

    def get_progress(self, task_id: str) -> Optional[dict]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        with self._locks.get(task_id, Lock()):
            percent = (task.bytes_downloaded / task.total_bytes * 100) if task.total_bytes else 0
            return {
                "id": task_id,
                "url": task.url,
                "dest": str(task.dest_path),
                "status": task.status.value,
                "downloaded": task.bytes_downloaded,
                "total": task.total_bytes,
                "percent": percent,
                "error": task.error,
                "type": task.download_type.value,
                "title": task.title,
                "format": task.video_format.value if task.video_format else None,
                "quality": task.video_quality.value if task.video_quality else None,
            }

    def get_all_tasks(self) -> list:
        return [self.get_progress(tid) for tid in self._tasks.keys()]

    def set_max_speed(self, bytes_per_second: int):
        self._max_speed = bytes_per_second

    def set_default_path(self, path: str):
        self._default_save_path = Path(path)
        self._default_save_path.mkdir(exist_ok=True)

    def _video_download_worker(self, task_id: str):
        self._active_semaphore.acquire()
        
        try:
            task = self._tasks.get(task_id)
            if not task:
                return

            task.status = Status.EXTRACTING
            self._events.emit(EventType.PROGRESS, {
                "id": task_id,
                "status": "extracting",
                "percent": 0,
                "message": "Получение информации о видео..."
            })

            downloader = YTDLPDownloader(
                task=task,
                events=self._events,
                pause_event=self._pause_events[task_id],
                cancel_event=self._cancel_events[task_id],
                progress_callback=self._emit_progress,
            )
            
            success, result = downloader.download()

        except Exception as e:
            task = self._tasks.get(task_id)
            if task:
                task.status = Status.ERROR
                task.error = str(e)
            self._events.emit(EventType.ERROR, {
                "id": task_id, 
                "error": str(e)
            })
        finally:
            self._active_semaphore.release()

    def _http_download_worker(self, task_id: str):
        self._active_semaphore.acquire()
        
        try:
            task = self._tasks.get(task_id)
            if not task:
                return

            part_file = Path(str(task.dest_path) + ".part")
            resume_pos = 0

            if part_file.exists():
                resume_pos = part_file.stat().st_size
                if resume_pos > 0:
                    self._resume_positions[task_id] = resume_pos

            headers = {"Range": f"bytes={resume_pos}-"} if resume_pos else {}
            task.status = Status.DOWNLOADING

            with requests.get(task.url, headers=headers, stream=True, timeout=60) as resp:
                if resp.status_code == 416:
                    resume_pos = 0
                    headers = {}
                    task.bytes_downloaded = 0
                
                if resp.status_code in (200, 206):
                    if "Content-Length" in resp.headers:
                        task.total_bytes = int(resp.headers["Content-Length"]) + resume_pos

                    mode = "ab" if resume_pos > 0 else "wb"
                    
                    with open(part_file, mode) as f:
                        last_update = time.time()
                        
                        for chunk in resp.iter_content(chunk_size=65536):
                            if self._cancel_events[task_id].is_set():
                                return

                            while task.status == Status.PAUSED:
                                self._pause_events[task_id].wait()
                                if self._cancel_events[task_id].is_set():
                                    return

                            if chunk:
                                limit = task.speed_limit or self._max_speed
                                if limit > 0:
                                    self._apply_rate_limit(len(chunk), limit, task_id)

                                f.write(chunk)
                                
                                with self._locks.get(task_id, Lock()):
                                    task.bytes_downloaded += len(chunk)

                                current_time = time.time()
                                if current_time - last_update >= 0.25:
                                    self._events.emit(EventType.PROGRESS, {
                                        "id": task_id,
                                        "downloaded": task.bytes_downloaded,
                                        "total": task.total_bytes,
                                        "percent": task.bytes_downloaded / task.total_bytes * 100 if task.total_bytes else 0
                                    })
                                    last_update = current_time

            part_file.rename(task.dest_path)
            task.status = Status.COMPLETED
            self._events.emit(EventType.COMPLETED, {
                "id": task_id, 
                "path": str(task.dest_path)
            })

        except Exception as e:
            task = self._tasks.get(task_id)
            if task:
                task.status = Status.ERROR
                task.error = str(e)
            self._events.emit(EventType.ERROR, {
                "id": task_id, 
                "error": str(e)
            })
        finally:
            self._active_semaphore.release()

    def _emit_progress(self, data: dict):
        self._events.emit(EventType.PROGRESS, data)

    def _apply_rate_limit(self, bytes_written: int, limit: int, task_id: str):
        max_time = bytes_written / limit
        sleep_time = max_time
        check_interval = 0.05
        elapsed = 0
        
        while elapsed < sleep_time:
            if self._cancel_events.get(task_id, Event()).is_set():
                break
            time.sleep(min(check_interval, sleep_time - elapsed))
            elapsed += check_interval

    def _extract_filename(self, url: str) -> str:
        path = url.split("/")[-1]
        name = path.split("?")[0]
        return name if name else f"download_{int(time.time())}"

    def cleanup_completed(self):
        completed = [tid for tid, t in self._tasks.items() 
                    if t.status in (Status.COMPLETED, Status.CANCELLED, Status.ERROR)]
        for tid in completed:
            self._tasks.pop(tid, None)
            self._threads.pop(tid, None)
            self._pause_events.pop(tid, None)
            self._cancel_events.pop(tid, None)
            self._locks.pop(tid, None)

    def reset_instance(self):
        cls = type(self)
        if cls._instance is not None:
            cls._instance._initialized = False
            cls._instance = None
