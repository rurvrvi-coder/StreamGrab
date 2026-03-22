import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable
from pathlib import Path
import queue
import sys

from downloader.thread_pool import (
    ThreadPool,
    DownloadScheduler,
    DownloadJob,
    TaskPriority,
)
from downloader.url_parser import URLParser
from downloader.ytdlp_downloader import VideoInfoExtractor
from downloader.file_handler import FolderManager, FileTypeDetector, FileCategory
from downloader.segmented_downloader import SegmentDownloader, SegmentedDownloadManager
from downloader.models import VideoFormat, VideoQuality
from downloader.logger import get_logger, LogLevel, ErrorHandler
from downloader.settings import (
    SettingsManager,
    get_settings,
    save_settings,
    AppSettings,
)

LOGGER = get_logger("StreamGrab-GUI")
ERROR_HANDLER = ErrorHandler(LOGGER)

try:
    from plyer import notification

    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False


def send_notification(title: str, message: str, urgency: str = "normal"):
    """Send system notification"""
    if NOTIFICATIONS_AVAILABLE:
        try:
            notification.notify(
                title=title, message=message, app_name="StreamGrab", timeout=10
            )
        except Exception:
            pass
    else:
        print(f"[NOTIFICATION] {title}: {message}")


@dataclass
class TaskInfo:
    task_id: str
    url: str
    title: str
    progress: float = 0.0
    status: str = "pending"
    speed: float = 0.0
    speed_avg: float = 0.0
    downloaded: float = 0.0
    total: float = 0.0
    eta: float = 0.0
    download_type: str = "http"
    category: str = "other"
    video_format: Optional[str] = None
    video_quality: Optional[str] = None
    error: Optional[str] = None
    segmented: bool = False
    num_segments: int = 0
    start_time: float = field(default_factory=time.time)
    _speed_samples: list = field(default_factory=list)


class AsyncDownloadManager:
    def __init__(self, max_concurrent: int = 10, num_segments: int = 8):
        self._pool = ThreadPool(num_workers=max_concurrent)
        self._scheduler = DownloadScheduler(self._pool, max_concurrent=max_concurrent)
        self._max_concurrent = max_concurrent
        self._num_segments = num_segments
        self._lock = threading.Lock()
        self._tasks: dict[str, TaskInfo] = {}
        self._callbacks: dict[str, list[Callable]] = {}
        self._progress_queue: queue.Queue = queue.Queue()
        self._folder_manager = FolderManager()
        self._segmented_manager = SegmentedDownloadManager(
            max_concurrent=max_concurrent, num_segments=num_segments
        )
        self._notifications_enabled = True
        self._notification_callbacks: list[Callable] = []

    @property
    def folder_manager(self) -> FolderManager:
        return self._folder_manager

    def enable_notifications(self, enabled: bool = True):
        self._notifications_enabled = enabled

    def on_notification(self, callback: Callable):
        self._notification_callbacks.append(callback)

    def _send_notification(self, task_id: str, title: str, message: str):
        if self._notifications_enabled:
            send_notification(title, message)

        for cb in self._notification_callbacks:
            try:
                cb(task_id, title, message)
            except Exception:
                pass

    def add_download(
        self,
        url: str,
        dest: Optional[str] = None,
        speed_limit: int = 0,
        video_format: Optional[str] = None,
        video_quality: Optional[str] = None,
        category: Optional[FileCategory] = None,
        use_segmentation: bool = True,
    ) -> str:

        task_id = f"task_{int(time.time() * 1000)}"

        download_type = "http"
        title = url.split("/")[-1][:50] or "download"

        if URLParser.is_supported_video(url):
            download_type = "video"

        cat = category
        if cat is None:
            cat, _, _ = FileTypeDetector.detect_from_url(url)

        dest_path = Path(dest) if dest else self._folder_manager.get_folder(cat) / title

        use_segment = use_segmentation and download_type == "http"

        if use_segment:
            segment_info = self._check_segmentation_support(url)
            use_segment = (
                segment_info["supports"] and segment_info["size"] >= 100 * 1024 * 1024
            )

        task_info = TaskInfo(
            task_id=task_id,
            url=url,
            title=title,
            progress=0.0,
            status="pending",
            speed=0.0,
            speed_avg=0.0,
            downloaded=0.0,
            total=0.0,
            eta=0.0,
            download_type=download_type,
            category=cat.value,
            video_format=video_format,
            video_quality=video_quality,
            segmented=use_segment,
            num_segments=self._num_segments if use_segment else 0,
            start_time=time.time(),
        )

        with self._lock:
            self._tasks[task_id] = task_info

        if use_segment:
            self._add_segmented_download(task_id, url, dest_path, speed_limit)
        else:
            self._add_http_download(task_id, url, dest_path, speed_limit)

        return task_id

    def _check_segmentation_support(self, url: str) -> dict:
        downloader = SegmentDownloader()
        size, supports = downloader.get_file_size(url)
        return {"size": size or 0, "supports": supports}

    def _add_segmented_download(
        self, task_id: str, url: str, dest_path: Path, speed_limit: int
    ):
        def progress_callback(data):
            self._progress_queue.put((task_id, data))

        def worker():
            downloader = SegmentDownloader(num_segments=self._num_segments)

            success, error = downloader.download(
                url=url,
                dest_path=dest_path,
                progress_callback=progress_callback,
                speed_limit=speed_limit,
            )

            with self._lock:
                if task_id in self._tasks:
                    if success:
                        self._tasks[task_id].status = "completed"
                        self._tasks[task_id].progress = 100.0
                        self._send_notification(
                            task_id,
                            "Загрузка завершена",
                            f"{self._tasks[task_id].title[:50]} успешно скачан",
                        )
                    else:
                        self._tasks[task_id].status = "error"
                        self._tasks[task_id].error = error
                        self._send_notification(
                            task_id,
                            "Ошибка загрузки",
                            f"{self._tasks[task_id].title[:50]}: {error}",
                        )

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _add_http_download(
        self, task_id: str, url: str, dest_path: Path, speed_limit: int
    ):
        def callback(data):
            self._progress_queue.put((task_id, callback))

        job = DownloadJob(
            priority=TaskPriority.NORMAL.value,
            task_id=task_id,
            url=url,
            dest=str(dest_path),
            speed_limit=speed_limit,
            download_type="http",
            video_format=None,
            video_quality=None,
            callback=callback,
        )

        self._scheduler.schedule(job)

    def process_updates(self) -> list[tuple[str, dict]]:
        updates = []
        while True:
            try:
                task_id, data = self._progress_queue.get_nowait()
                updates.append((task_id, data))

                with self._lock:
                    if task_id in self._tasks:
                        task = self._tasks[task_id]
                        task.status = data.get("status", task.status)
                        task.progress = data.get("percent", task.progress)
                        task.downloaded = data.get("downloaded", task.downloaded)
                        task.total = data.get("total", task.total)
                        task.speed = data.get("speed", task.speed) or 0

                        if "eta" in data:
                            task.eta = data["eta"]

                        task._speed_samples.append(task.speed)
                        if len(task._speed_samples) > 10:
                            task._speed_samples.pop(0)
                        task.speed_avg = (
                            sum(task._speed_samples) / len(task._speed_samples)
                            if task._speed_samples
                            else 0
                        )

                        if task.total > 0 and task.speed_avg > 0:
                            task.eta = (task.total - task.downloaded) / task.speed_avg
                        elif task.total > 0:
                            elapsed = time.time() - task.start_time
                            if elapsed > 0:
                                avg_speed = task.downloaded / elapsed
                                if avg_speed > 0:
                                    task.eta = (
                                        task.total - task.downloaded
                                    ) / avg_speed

                        if "error" in data:
                            task.error = data["error"]

            except queue.Empty:
                break
        return updates

    def get_all_tasks(self) -> list[TaskInfo]:
        with self._lock:
            return list(self._tasks.values())

    def get_stats(self) -> dict:
        with self._lock:
            active = self._pool.get_active_count()
            pending = self._scheduler.get_pending_count()
            total = len(self._tasks)
            return {
                "active": active,
                "pending": pending,
                "total": total,
                "max": self._max_concurrent,
            }

    def cancel_task(self, task_id: str) -> bool:
        result = self._scheduler.cancel(task_id)
        if result:
            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id].status = "cancelled"
        return result

    def shutdown(self):
        self._scheduler.shutdown()
        self._pool.shutdown()


class DownloadItemFrame(ttk.Frame):
    CATEGORY_ICONS = {
        "video": "🎬",
        "audio": "🎵",
        "image": "🖼",
        "document": "📄",
        "archive": "📦",
        "application": "⚙",
        "other": "📁",
    }

    def __init__(
        self,
        parent,
        task_id: str,
        title: str,
        url: str,
        category: str,
        segmented: bool,
        on_cancel: Callable,
    ):
        super().__init__(parent, relief="groove", borderwidth=1)

        self.task_id = task_id
        self.on_cancel = on_cancel
        self.category = category
        self.segmented = segmented

        self.columnconfigure(0, weight=1)

        top_frame = ttk.Frame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        top_frame.columnconfigure(0, weight=1)

        icon = self.CATEGORY_ICONS.get(category, "📁")
        seg_icon = " ⚡" if segmented else ""
        self.title_label = tk.Label(
            top_frame,
            text=f"{icon} {title}{seg_icon}",
            font=("Arial", 10, "bold"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.status_label = tk.Label(top_frame, text="⏳", font=("Arial", 12), width=3)
        self.status_label.grid(row=0, column=1, sticky="e")

        self.url_label = tk.Label(
            self, text=url[:70], font=("Arial", 8), fg="gray", anchor="w"
        )
        self.url_label.grid(row=1, column=0, sticky="w", padx=5)

        self.progress_bar = ttk.Progressbar(self, mode="determinate", length=100)
        self.progress_bar.grid(row=2, column=0, sticky="ew", padx=5, pady=2)

        bottom_frame = ttk.Frame(self)
        bottom_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 5))

        self.info_label = tk.Label(
            bottom_frame, text="0% • 0 B / 0 B", font=("Arial", 8)
        )
        self.info_label.pack(side="left")

        self.speed_label = tk.Label(
            bottom_frame, text="⬇ 0 KB/s", font=("Arial", 8, "bold"), fg="blue"
        )
        self.speed_label.pack(side="left", padx=10)

        self.eta_label = tk.Label(
            bottom_frame, text="⏱ —", font=("Arial", 8), fg="gray"
        )
        self.eta_label.pack(side="left", padx=10)

        self.cancel_btn = ttk.Button(
            bottom_frame,
            text="✕",
            width=3,
            command=lambda: self.on_cancel(self.task_id),
        )
        self.cancel_btn.pack(side="right")

    def update_progress(
        self,
        downloaded: float,
        total: float,
        progress: float,
        status: str,
        speed: float = 0,
        speed_avg: float = 0,
        eta: float = 0,
    ):
        self.progress_bar["value"] = progress
        self.status_label["text"] = self._get_status_icon(status)

        downloaded_str = self._format_size(downloaded)
        total_str = self._format_size(total)
        self.info_label["text"] = f"{progress:.1f}% • {downloaded_str} / {total_str}"

        if speed_avg > 0:
            speed_str = self._format_speed(speed_avg)
            self.speed_label["text"] = f"⬇ {speed_str}"
        elif speed > 0:
            speed_str = self._format_speed(speed)
            self.speed_label["text"] = f"⬇ {speed_str}"
        else:
            self.speed_label["text"] = "⬇ —"

        if eta > 0 and status == "downloading":
            eta_str = self._format_eta(eta)
            self.eta_label["text"] = f"⏱ {eta_str}"
        else:
            self.eta_label["text"] = "⏱ —"

        if status in ("completed", "cancelled", "error"):
            self.cancel_btn["state"] = "disabled"
            self.speed_label.pack_forget()
            self.eta_label.pack_forget()

    def _get_status_icon(self, status: str) -> str:
        icons = {
            "pending": "⏳",
            "downloading": "⬇",
            "paused": "⏸",
            "completed": "✅",
            "cancelled": "❌",
            "error": "⚠️",
        }
        return icons.get(status, "?")

    def _format_size(self, bytes_size: float) -> str:
        if bytes_size == 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"

    def _format_speed(self, bytes_per_sec: float) -> str:
        if bytes_per_sec == 0:
            return "0 B/s"
        for unit in ["B/s", "KB/s", "MB/s", "GB/s"]:
            if bytes_per_sec < 1024:
                return f"{bytes_per_sec:.1f} {unit}"
            bytes_per_sec /= 1024
        return f"{bytes_per_sec:.1f} GB/s"

    def _format_eta(self, seconds: float) -> str:
        if seconds <= 0 or seconds > 86400:
            return "—"
        if seconds < 60:
            return f"{int(seconds)} сек"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins} мин {secs} сек"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours} ч {mins} мин"


class SettingsDialog(tk.Toplevel):
    def __init__(
        self, parent, settings_manager: SettingsManager, folder_manager: FolderManager
    ):
        super().__init__(parent)

        self.settings_manager = settings_manager
        self.settings = self.settings_manager.settings
        self.folder_manager = folder_manager
        self.result = None

        self.title("Настройки")
        self.geometry("550x550")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(
            main_frame, text="Настройки загрузок", font=("Arial", 14, "bold")
        ).pack(pady=(0, 20))

        path_frame = ttk.LabelFrame(main_frame, text="Базовая папка", padding=10)
        path_frame.pack(fill="x", pady=(0, 15))

        path_inner = ttk.Frame(path_frame)
        path_inner.pack(fill="x")

        self.path_var = tk.StringVar(value=self.settings.download_folder)
        path_entry = ttk.Entry(path_inner, textvariable=self.path_var, width=40)
        path_entry.pack(side="left", fill="x", expand=True)

        ttk.Button(path_inner, text="...", width=3, command=self._browse_path).pack(
            side="left", padx=(5, 0)
        )

        segment_frame = ttk.LabelFrame(main_frame, text="Сегментация", padding=10)
        segment_frame.pack(fill="x", pady=(0, 15))

        seg_inner = ttk.Frame(segment_frame)
        seg_inner.pack(fill="x")

        ttk.Label(seg_inner, text="Количество сегментов:").pack(side="left")

        self.segments_var = tk.IntVar(value=self.settings.num_segments)
        segments_spin = ttk.Spinbox(
            seg_inner, from_=2, to=16, textvariable=self.segments_var, width=5
        )
        segments_spin.pack(side="left", padx=10)

        ttk.Label(
            seg_inner,
            text="(для файлов > 100 MB)",
            font=("Arial", 8),
            foreground="gray",
        ).pack(side="left")

        notif_frame = ttk.LabelFrame(main_frame, text="Уведомления", padding=10)
        notif_frame.pack(fill="x", pady=(0, 15))

        self.notif_var = tk.BooleanVar(value=self.settings.notifications_enabled)
        notif_check = ttk.Checkbutton(
            notif_frame,
            text="Показывать системные уведомления при завершении загрузки",
            variable=self.notif_var,
        )
        notif_check.pack(anchor="w")

        categories_frame = ttk.LabelFrame(
            main_frame, text="Папки по категориям", padding=10
        )
        categories_frame.pack(fill="both", expand=True, pady=(0, 15))

        categories = [
            ("Videos", FileCategory.VIDEO),
            ("Music", FileCategory.AUDIO),
            ("Images", FileCategory.IMAGE),
            ("Documents", FileCategory.DOCUMENT),
            ("Archives", FileCategory.ARCHIVE),
        ]

        self.category_vars = {}
        for name, cat in categories:
            cat_name = cat.value
            folder_name = self.settings.category_folders.get(cat_name, "Downloads")
            default_path = str(Path(self.settings.download_folder) / folder_name)
            var = tk.StringVar(value=default_path)
            frame = ttk.Frame(categories_frame)
            frame.pack(fill="x", pady=2)

            ttk.Label(frame, text=f"{name}:", width=15).pack(side="left")
            ttk.Entry(frame, textvariable=var, width=30).pack(
                side="left", fill="x", expand=True
            )
            self.category_vars[cat] = var

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Сброс", command=self._reset).pack(side="left")
        ttk.Button(btn_frame, text="Сохранить", command=self._save).pack(
            side="right", padx=(5, 0)
        )
        ttk.Button(btn_frame, text="Отмена", command=self.destroy).pack(side="right")

    def _browse_path(self):
        folder = filedialog.askdirectory(title="Выберите базовую папку")
        if folder:
            self.path_var.set(folder)

    def _reset(self):
        if messagebox.askyesno(
            "Сброс настроек", "Вы уверены, что хотите сбросить все настройки?"
        ):
            self.settings_manager.reset()
            self.result = "reset"
            self.destroy()

    def _save(self):
        self.settings.download_folder = self.path_var.get()
        self.settings.num_segments = self.segments_var.get()
        self.settings.notifications_enabled = self.notif_var.get()
        self.settings.category_folders = {
            cat.value: str(Path(var.get()).name)
            for cat, var in self.category_vars.items()
        }
        self.settings_manager.save(self.settings)
        self.result = {
            "download_folder": self.path_var.get(),
            "num_segments": self.segments_var.get(),
            "notifications_enabled": self.notif_var.get(),
        }
        self.destroy()


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("StreamGrab - Video Downloader")
        self.root.geometry("850x700")
        self.root.minsize(750, 500)

        self.settings_manager = get_settings_manager()
        self.settings = self.settings_manager.load()

        self.num_segments = self.settings.num_segments
        self.notifications_enabled = self.settings.notifications_enabled
        self.manager = AsyncDownloadManager(
            max_concurrent=self.settings.max_concurrent,
            num_segments=self.settings.num_segments,
        )

        if Path(self.settings.download_folder).exists():
            self.manager.folder_manager.set_base_path(self.settings.download_folder)

        self.task_frames: dict[str, DownloadItemFrame] = {}
        self._last_notification_time: dict[str, float] = {}

        self._setup_styles()
        self._create_widgets()
        self._start_update_loop()

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Arial", 14, "bold"))
        style.configure("Status.TLabel", font=("Arial", 10))
        style.configure("Info.TLabel", font=("Arial", 9))

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))

        title_label = ttk.Label(header_frame, text="StreamGrab", style="Title.TLabel")
        title_label.pack(side="left")

        self.stats_label = ttk.Label(
            header_frame, text="Активных: 0/10", style="Status.TLabel"
        )
        self.stats_label.pack(side="right")

        self.status_bar = tk.Label(header_frame, text="", fg="red", font=("Arial", 9))
        self.status_bar.pack(side="left", padx=20)

        input_frame = ttk.LabelFrame(main_frame, text="Новая загрузка", padding=10)
        input_frame.pack(fill="x", pady=(0, 10))

        self.url_entry = ttk.Entry(input_frame)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.url_entry.bind("<Return>", lambda e: self._add_download())

        self.format_combo = ttk.Combobox(input_frame, width=10, state="readonly")
        self.format_combo["values"] = [
            "Best",
            "MP4",
            "WebM",
            "MKV",
            "MP3",
            "WAV",
            "FLAC",
            "M4A",
        ]
        self.format_combo.current(0)
        self.format_combo.pack(side="left", padx=5)

        self.quality_combo = ttk.Combobox(input_frame, width=10, state="readonly")
        self.quality_combo["values"] = [
            "Best",
            "2160p",
            "1440p",
            "1080p",
            "720p",
            "480p",
            "360p",
            "240p",
        ]
        self.quality_combo.current(0)
        self.quality_combo.pack(side="left", padx=(0, 5))

        self.add_btn = ttk.Button(
            input_frame, text="Добавить", command=self._add_download
        )
        self.add_btn.pack(side="left")

        list_frame = ttk.LabelFrame(main_frame, text="Загрузки", padding=5)
        list_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(list_frame, bg="#f5f5f5")
        self.scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )

        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill="x", pady=(10, 0))

        self.folder_label = ttk.Label(
            controls_frame,
            text=f"📁 {self.manager.folder_manager.base_path}",
            style="Info.TLabel",
        )
        self.folder_label.pack(side="left")

        ttk.Button(controls_frame, text="📂 Папка", command=self._choose_folder).pack(
            side="left", padx=5
        )

        self.segments_label = ttk.Label(
            controls_frame,
            text=f"⚡ Сегментов: {self.num_segments}",
            style="Info.TLabel",
        )
        self.segments_label.pack(side="left", padx=10)

        self.notif_label = ttk.Label(
            controls_frame,
            text="🔔" if self.notifications_enabled else "🔕",
            style="Info.TLabel",
        )
        self.notif_label.pack(side="left", padx=5)

        ttk.Button(controls_frame, text="⚙", width=2, command=self._open_settings).pack(
            side="left", padx=2
        )

        ttk.Separator(controls_frame, orient="vertical").pack(
            side="left", padx=10, fill="y"
        )

        ttk.Button(
            controls_frame, text="🗑 Очистить", command=self._clear_completed
        ).pack(side="right")

        self.queue_label = ttk.Label(
            controls_frame, text="В очереди: 0", style="Status.TLabel"
        )
        self.queue_label.pack(side="right", padx=10)

    def _add_download(self):
        url = self.url_entry.get().strip()
        if not url:
            return

        if not URLParser.is_valid_url(url):
            error_info = ERROR_HANDLER.handle(
                ValueError("Invalid URL"), "Валидация URL"
            )
            messagebox.showerror(
                "Ошибка", f"{error_info['message']}\n{error_info['action']}"
            )
            LOGGER.error(f"Некорректный URL: {url}")
            return

        video_format = None
        video_quality = None
        category = None
        download_type = "HTTP"

        if URLParser.is_supported_video(url):
            download_type = "Video"
            format_map = {
                "Best": "best",
                "MP4": "mp4",
                "WebM": "webm",
                "MKV": "mkv",
                "MP3": "mp3",
                "WAV": "wav",
                "FLAC": "flac",
                "M4A": "m4a",
            }
            quality_map = {
                "Best": "best",
                "2160p": "2160",
                "1440p": "1440",
                "1080p": "1080",
                "720p": "720",
                "480p": "480",
                "360p": "360",
                "240p": "240",
            }

            video_format = format_map.get(self.format_combo.get(), "best")
            video_quality = quality_map.get(self.quality_combo.get(), "best")

            if video_format in ("mp3", "wav", "flac", "m4a"):
                category = FileCategory.AUDIO
                download_type = "Audio"
            else:
                category = FileCategory.VIDEO
        else:
            cat, _, _ = FileTypeDetector.detect_from_url(url)
            category = cat

        try:
            success, info, _ = VideoInfoExtractor.get_video_info(url)
            if success and info:
                title = info.title[:50] if len(info.title) > 50 else info.title
                LOGGER.info(f"Добавлена загрузка [{download_type}]: {title}")
            else:
                title = url.split("/")[-1][:50] or "download"
                LOGGER.info(f"Добавлена загрузка [HTTP]: {title}")
        except Exception as e:
            error_info = ERROR_HANDLER.handle(e, "Получение информации о видео")
            title = url.split("/")[-1][:50] or "download"
            LOGGER.warning(
                f"Не удалось получить информацию о видео: {error_info['message']}"
            )

        try:
            task_id = self.manager.add_download(
                url,
                video_format=video_format,
                video_quality=video_quality,
                category=category,
            )

            tasks = self.manager.get_all_tasks()
            task_data = next((t for t in tasks if t.task_id == task_id), None)
            segmented = task_data.segmented if task_data else False

            self._create_task_frame(
                task_id, title, url, category.value if category else "other", segmented
            )
            self.url_entry.delete(0, tk.END)

        except Exception as e:
            error_info = ERROR_HANDLER.handle(e, "Добавление загрузки")
            messagebox.showerror(
                "Ошибка", f"{error_info['message']}\n{error_info['action']}"
            )
            LOGGER.error(f"Ошибка добавления загрузки: {url}")

    def _create_task_frame(
        self, task_id: str, title: str, url: str, category: str, segmented: bool
    ):
        frame = DownloadItemFrame(
            self.scrollable_frame,
            task_id,
            title,
            url,
            category,
            segmented,
            on_cancel=self._cancel_task,
        )
        frame.pack(fill="x", padx=5, pady=5)
        self.task_frames[task_id] = frame

    def _cancel_task(self, task_id: str):
        self.manager.cancel_task(task_id)
        if task_id in self.task_frames:
            self.task_frames[task_id].destroy()
            del self.task_frames[task_id]

    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Выберите папку для загрузок")
        if folder:
            self.manager.folder_manager.set_base_path(folder)
            self.folder_label["text"] = f"📁 {folder}"

    def _open_settings(self):
        dialog = SettingsDialog(
            self.root, self.settings_manager, self.manager.folder_manager
        )
        self.root.wait_window(dialog)

        if dialog.result == "reset":
            self.settings = self.settings_manager.load()
        elif dialog.result:
            self.settings = self.settings_manager.settings
            self.num_segments = self.settings.num_segments
            self.notifications_enabled = self.settings.notifications_enabled
            self.manager.folder_manager.set_base_path(self.settings.download_folder)
            self.manager.enable_notifications(self.notifications_enabled)

        self.segments_label["text"] = f"⚡ Сегментов: {self.num_segments}"
        self.folder_label["text"] = f"📁 {self.settings.download_folder}"
        self.notif_label["text"] = "🔔" if self.notifications_enabled else "🔕"

    def _clear_completed(self):
        to_remove = []
        tasks = self.manager.get_all_tasks()

        for task_id, frame in self.task_frames.items():
            task_data = next((t for t in tasks if t.task_id == task_id), None)
            if task_data and task_data.status in ("completed", "cancelled", "error"):
                to_remove.append(task_id)

        for task_id in to_remove:
            if task_id in self.task_frames:
                self.task_frames[task_id].destroy()
                del self.task_frames[task_id]

    def _start_update_loop(self):
        def update():
            try:
                updates = self.manager.process_updates()

                for task_id, data in updates:
                    if task_id in self.task_frames:
                        tasks = self.manager.get_all_tasks()
                        task_data = next(
                            (t for t in tasks if t.task_id == task_id), None
                        )
                        if task_data:
                            self.task_frames[task_id].update_progress(
                                task_data.downloaded,
                                task_data.total,
                                task_data.progress,
                                task_data.status,
                                task_data.speed,
                                task_data.speed_avg,
                                task_data.eta,
                            )

                            current_time = time.time()
                            last_time = self._last_notification_time.get(task_id, 0)

                            if (
                                task_data.status == "completed"
                                and current_time - last_time > 5
                            ):
                                self._last_notification_time[task_id] = current_time
                                LOGGER.info(f"Загрузка завершена: {task_data.title}")
                                self.status_bar.configure(
                                    text="✅ Загрузка завершена", fg="green"
                                )
                                self.root.after(
                                    3000, lambda: self.status_bar.configure(text="")
                                )

                            elif task_data.status == "error":
                                error_msg = task_data.error or "Неизвестная ошибка"
                                if current_time - last_time > 5:
                                    self._last_notification_time[task_id] = current_time
                                    LOGGER.error(
                                        f"Ошибка загрузки: {task_data.title} - {error_msg}"
                                    )
                                    self.status_bar.configure(
                                        text=f"⚠️ {error_msg}", fg="red"
                                    )
                                    self.root.after(
                                        5000, lambda: self.status_bar.configure(text="")
                                    )

                stats = self.manager.get_stats()
                self.stats_label["text"] = f"Активных: {stats['active']}/{stats['max']}"
                self.queue_label["text"] = f"В очереди: {stats['pending']}"

            except Exception as e:
                ERROR_HANDLER.handle(e, "Update loop")

            self.root.after(100, update)

        update()

    def run(self):
        self.root.mainloop()
        self.manager.shutdown()


def main():
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
