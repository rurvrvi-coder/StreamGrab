import queue
import threading
import time
import requests
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TaskPriority(Enum):
    HIGH = 0
    NORMAL = 1
    LOW = 2


@dataclass(order=True)
class DownloadJob:
    priority: int
    task_id: str = field(compare=False)
    url: str = field(compare=False)
    dest: Optional[str] = field(compare=False)
    speed_limit: int = field(compare=False)
    download_type: str = field(compare=False)
    video_format: Optional[str] = field(compare=False)
    video_quality: Optional[str] = field(compare=False)
    callback: Optional[Callable] = field(compare=False, default=None)


class ThreadPool:
    def __init__(self, num_workers: int = 10):
        self._num_workers = num_workers
        self._workers: list[threading.Thread] = []
        self._job_queue: queue.PriorityQueue[DownloadJob] = queue.PriorityQueue()
        self._task_results: Dict[str, Any] = {}
        self._results_lock = threading.Lock()
        self._workers_lock = threading.Lock()
        self._shutdown = threading.Event()
        self._active_tasks = 0
        self._active_lock = threading.Lock()
        self._task_locks: Dict[str, threading.Lock] = {}

        self._start_workers()

    def _start_workers(self):
        for i in range(self._num_workers):
            worker = threading.Thread(
                target=self._worker_loop, name=f"Worker-{i + 1}", daemon=True
            )
            worker.start()
            self._workers.append(worker)

    def _worker_loop(self):
        while not self._shutdown.is_set():
            try:
                job = self._job_queue.get(timeout=0.5)

                with self._active_lock:
                    self._active_tasks += 1

                try:
                    self._execute_job(job)
                finally:
                    with self._active_lock:
                        self._active_tasks -= 1
                    self._job_queue.task_done()

            except queue.Empty:
                continue

    def _execute_job(self, job: DownloadJob):
        try:
            result = self._download_file(job)

            with self._results_lock:
                self._task_results[job.task_id] = {
                    "status": "completed",
                    "result": result,
                    "completed_at": time.time(),
                }

            if job.callback:
                job.callback(
                    {"id": job.task_id, "status": "completed", "result": result}
                )

        except Exception as e:
            with self._results_lock:
                self._task_results[job.task_id] = {
                    "status": "error",
                    "error": str(e),
                    "completed_at": time.time(),
                }

            if job.callback:
                job.callback({"id": job.task_id, "status": "error", "error": str(e)})

    def _download_file(self, job: DownloadJob) -> dict:
        dest_path = (
            Path(job.dest)
            if job.dest
            else Path.home() / "Downloads" / f"{job.task_id}.bin"
        )
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        total_size = 0
        last_update = time.time()
        start_time = time.time()

        headers = {}
        resume_pos = 0

        if dest_path.exists():
            resume_pos = dest_path.stat().st_size
            headers["Range"] = f"bytes={resume_pos}-"

        try:
            response = requests.get(job.url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get("Content-Length", 0)) + resume_pos

            mode = "ab" if resume_pos > 0 else "wb"

            with open(dest_path, mode) as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if self._shutdown.is_set():
                        break

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        current_time = time.time()
                        if current_time - last_update >= 0.25:
                            elapsed = current_time - start_time
                            speed = downloaded / elapsed if elapsed > 0 else 0

                            progress_data = {
                                "id": job.task_id,
                                "status": "downloading",
                                "downloaded": downloaded,
                                "total": total_size,
                                "percent": (downloaded / total_size * 100)
                                if total_size > 0
                                else 0,
                                "speed": speed,
                            }

                            with self._results_lock:
                                self._task_results[job.task_id] = progress_data.copy()

                            if job.callback:
                                job.callback(progress_data)

                            last_update = current_time

        except requests.exceptions.ConnectionError as e:
            raise Exception(f"Ошибка подключения: {e}")
        except requests.exceptions.Timeout as e:
            raise Exception(f"Таймаут: {e}")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"HTTP ошибка: {e}")
        except Exception as e:
            raise Exception(f"Ошибка загрузки: {e}")

        return {"path": str(dest_path), "size": downloaded}

    def submit(self, job: DownloadJob):
        self._task_locks[job.task_id] = threading.Lock()
        self._job_queue.put(job)

    def get_status(self, task_id: str) -> Optional[dict]:
        with self._results_lock:
            return self._task_results.get(task_id, {}).copy()

    def cancel_task(self, task_id: str) -> bool:
        with self._results_lock:
            if task_id in self._task_results:
                self._task_results[task_id]["status"] = "cancelled"
                return True
        return False

    def get_queue_size(self) -> int:
        return self._job_queue.qsize()

    def get_active_count(self) -> int:
        with self._active_lock:
            return self._active_tasks

    def shutdown(self, wait: bool = True):
        self._shutdown.set()
        if wait:
            for worker in self._workers:
                worker.join(timeout=2)


class DownloadScheduler:
    def __init__(self, pool: ThreadPool, max_concurrent: int = 10):
        self._pool = pool
        self._max_concurrent = max_concurrent
        self._pending_queue: queue.Queue[DownloadJob] = queue.Queue()
        self._scheduled: Dict[str, DownloadJob] = {}
        self._lock = threading.Lock()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False

    def schedule(self, job: DownloadJob):
        with self._lock:
            self._scheduled[job.task_id] = job
            self._pending_queue.put(job)

        self._start_scheduler()

    def _start_scheduler(self):
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return

        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._schedule_loop, daemon=True
        )
        self._scheduler_thread.start()

    def _schedule_loop(self):
        while self._running:
            try:
                if self._pool.get_active_count() < self._max_concurrent:
                    try:
                        job = self._pending_queue.get(timeout=0.5)
                        self._pool.submit(job)
                    except queue.Empty:
                        pass
                else:
                    time.sleep(0.1)

            except Exception:
                pass

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._scheduled:
                job = self._scheduled.pop(task_id)
                return self._pool.cancel_task(task_id)
        return False

    def get_pending_count(self) -> int:
        return self._pending_queue.qsize()

    def shutdown(self):
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=1)
