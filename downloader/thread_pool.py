import queue
import threading
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import time


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
        self._task_conditions: Dict[str, threading.Condition] = {}
        
        self._start_workers()
    
    def _start_workers(self):
        for i in range(self._num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"Worker-{i+1}",
                daemon=True
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
        task_lock = self._task_locks.get(job.task_id)
        task_condition = self._task_conditions.get(job.task_id)
        
        try:
            result = self._simulate_download(job)
            
            with self._results_lock:
                self._task_results[job.task_id] = {
                    "status": "completed",
                    "result": result,
                    "completed_at": time.time()
                }
            
            if job.callback:
                job.callback({
                    "id": job.task_id,
                    "status": "completed",
                    "result": result
                })
                
        except Exception as e:
            with self._results_lock:
                self._task_results[job.task_id] = {
                    "status": "error",
                    "error": str(e),
                    "completed_at": time.time()
                }
            
            if job.callback:
                job.callback({
                    "id": job.task_id,
                    "status": "error",
                    "error": str(e)
                })
    
    def _simulate_download(self, job: DownloadJob) -> dict:
        task_lock = self._task_locks.get(job.task_id)
        
        total_size = 50 * 1024 * 1024
        chunk_size = 1024 * 1024
        downloaded = 0
        
        while downloaded < total_size:
            if task_lock and not task_lock.locked():
                with self._results_lock:
                    if job.task_id in self._task_results:
                        if self._task_results[job.task_id].get("status") == "cancelled":
                            raise Exception("Task cancelled")
            
            time.sleep(0.1)
            downloaded += chunk_size
            
            progress = min(downloaded / total_size * 100, 100)
            
            with self._results_lock:
                self._task_results[job.task_id] = {
                    "status": "downloading",
                    "downloaded": downloaded,
                    "total": total_size,
                    "percent": progress
                }
            
            if job.callback:
                job.callback({
                    "id": job.task_id,
                    "status": "downloading",
                    "downloaded": downloaded,
                    "total": total_size,
                    "percent": progress
                })
        
        return {
            "path": job.dest or f"downloads/{job.task_id}.bin",
            "size": total_size
        }
    
    def submit(self, job: DownloadJob):
        self._task_locks[job.task_id] = threading.Lock()
        self._task_conditions[job.task_id] = threading.Condition(self._task_locks[job.task_id])
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
            target=self._schedule_loop,
            daemon=True
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
