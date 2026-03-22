import yt_dlp
from yt_dlp import utils
from pathlib import Path
from typing import Optional, Dict, Callable, Tuple, List, Any
import threading

from .url_parser import URLParser
from .models import DownloadTask, Status, VideoInfo, VideoFormat, VideoQuality, FileCategory
from .events import EventEmitter, EventType
from .file_handler import FolderManager


class YTDLPDownloader:
    def __init__(self, task: DownloadTask, 
                 events: EventEmitter,
                 pause_event: threading.Event,
                 cancel_event: threading.Event,
                 folder_manager: FolderManager,
                 progress_callback: Optional[Callable] = None):
        self.task = task
        self.events = events
        self.pause_event = pause_event
        self.cancel_event = cancel_event
        self.progress_callback = progress_callback
        self.folder_manager = folder_manager
        self._stop_download = False

    def _progress_hook(self, d: Dict[str, Any]):
        if self.cancel_event.is_set():
            self._stop_download = True
            raise utils.DownloadCancelled("User cancelled")

        while self.task.status == Status.PAUSED and not self.cancel_event.is_set():
            self.pause_event.wait()

        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed", 0)
            
            self.task.bytes_downloaded = downloaded
            self.task.total_bytes = total
            
            if self.progress_callback:
                self.progress_callback({
                    "id": self.task.id,
                    "downloaded": downloaded,
                    "total": total,
                    "percent": (downloaded / total * 100) if total > 0 else 0,
                    "speed": speed,
                    "eta": d.get("eta"),
                    "filename": d.get("filename")
                })

        elif d.get("status") == "finished":
            self.task.bytes_downloaded = d.get("downloaded_bytes", 0)
            self.task.total_bytes = d.get("total_bytes", 0)

        elif d.get("status") == "error":
            raise Exception(d.get("error", "Unknown download error"))

    def _get_category_for_format(self, video_format: Optional[VideoFormat]) -> FileCategory:
        if video_format in (VideoFormat.MP3, VideoFormat.WAV, VideoFormat.FLAC, VideoFormat.M4A, VideoFormat.OPUS):
            return FileCategory.AUDIO
        return FileCategory.VIDEO

    def _get_output_template(self) -> str:
        category = self._get_category_for_format(self.task.video_format)
        folder = self.folder_manager.get_folder(category)
        return str(folder / "%(title)s.%(ext)s")

    def _build_format_string(self) -> str:
        fmt = self.task.video_format
        qual = self.task.video_quality
        
        if fmt == VideoFormat.BEST:
            if qual == VideoQuality.BEST or qual is None:
                return "best"
            return f"bestvideo[height<={qual.value}]+bestaudio/best"
        
        if fmt in (VideoFormat.MP3, VideoFormat.WAV, VideoFormat.FLAC, VideoFormat.M4A, VideoFormat.OPUS):
            return "bestaudio/best"
        
        if fmt == VideoFormat.MP4:
            base = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
        elif fmt == VideoFormat.WEBM:
            base = "bestvideo[ext=webm]+bestaudio[ext=webm]/webm"
        elif fmt == VideoFormat.MKV:
            base = "bestvideo+bestaudio/best"
        else:
            base = "best"
        
        if qual and qual != VideoQuality.BEST:
            return f"bestvideo[height<={qual.value}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={qual.value}]+bestaudio/best[height<={qual.value}]"
        
        return base

    def download(self) -> Tuple[bool, Optional[str]]:
        try:
            output_template = self._get_output_template()
            format_spec = self._build_format_string()

            ydl_opts: Dict[str, Any] = {
                "format": format_spec,
                "outtmpl": output_template,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [self._progress_hook],
                "socket_timeout": 30,
                "merge_output_format": "mp4",
            }

            postprocessors = []
            
            if self.task.video_format == VideoFormat.MP3:
                postprocessors.append({
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                })
            elif self.task.video_format == VideoFormat.WAV:
                postprocessors.append({
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                })
            elif self.task.video_format == VideoFormat.FLAC:
                postprocessors.append({
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "flac",
                })
            elif self.task.video_format == VideoFormat.M4A:
                postprocessors.append({
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "192",
                })
            elif self.task.video_format == VideoFormat.OPUS:
                postprocessors.append({
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "opus",
                    "preferredquality": "128",
                })
            
            if self.task.video_format in (VideoFormat.MP3, VideoFormat.WAV, VideoFormat.FLAC, VideoFormat.M4A, VideoFormat.OPUS):
                postprocessors.append({
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                })
            
            if postprocessors:
                ydl_opts["postprocessors"] = postprocessors

            if self.task.speed_limit > 0:
                ydl_opts["ratelimit"] = self.task.speed_limit

            self.task.status = Status.DOWNLOADING
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.task.url, download=True)
                
                if info:
                    self.task.title = info.get("title", "")
                    self.task.thumbnail = info.get("thumbnail")
                    self.task.duration = info.get("duration")
                    self.task._ytdlp_info = info
                    
                    entries = info.get("entries")
                    if entries:
                        info = entries[0] if entries else info
                    
                    final_filename = ydl.prepare_filename(info)
                    final_path = Path(final_filename)
                    
                    if not final_path.exists():
                        possible_exts = ["mp4", "mkv", "webm", "mp3", "wav", "flac", "m4a", "opus", "webma"]
                        for ext in possible_exts:
                            alt_path = final_path.with_suffix(f".{ext}")
                            if alt_path.exists():
                                final_path = alt_path
                                break
                    
                    self.task.dest_path = final_path
                    self.task.file_category = self._get_category_for_format(self.task.video_format)
                    
            if not self._stop_download:
                self.task.status = Status.COMPLETED
                self.events.emit(EventType.COMPLETED, {
                    "id": self.task.id,
                    "path": str(self.task.dest_path),
                    "title": self.task.title,
                    "category": self.task.file_category.value
                })
                return True, str(self.task.dest_path)
            else:
                self.task.status = Status.CANCELLED
                return False, None

        except utils.DownloadCancelled:
            self.task.status = Status.CANCELLED
            return False, None
        except utils.DownloadError as e:
            self.task.status = Status.ERROR
            self.task.error = str(e)
            self.events.emit(EventType.ERROR, {
                "id": self.task.id,
                "error": str(e)
            })
            return False, str(e)
        except Exception as e:
            self.task.status = Status.ERROR
            self.task.error = str(e)
            self.events.emit(EventType.ERROR, {
                "id": self.task.id,
                "error": str(e)
            })
            return False, str(e)


class VideoInfoExtractor:
    @staticmethod
    def get_video_info(url: str) -> Tuple[bool, Optional[VideoInfo], Optional[str]]:
        try:
            ydl_opts: Dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "socket_timeout": 30,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return False, None, "Не удалось получить информацию о видео"
                
                entries = info.get("entries")
                if entries:
                    info = entries[0] if entries else info
                
                formats = info.get("formats") or []
                
                video_info = VideoInfo(
                    url=url,
                    title=info.get("title", "Неизвестно") or "Неизвестно",
                    thumbnail=info.get("thumbnail"),
                    duration=info.get("duration"),
                    formats=formats,
                    is_playlist=entries is not None,
                    playlist_count=len(entries) if entries else 0,
                    uploader=info.get("uploader") or info.get("channel"),
                    description=info.get("description", "")[:500] if info.get("description") else None,
                    upload_date=info.get("upload_date"),
                    view_count=info.get("view_count"),
                    like_count=info.get("like_count"),
                )
                
                return True, video_info, None
                
        except utils.DownloadError as e:
            return False, None, f"Ошибка загрузки: {str(e)}"
        except utils.ExtractorError as e:
            return False, None, f"Ошибка извлечения: {str(e)}"
        except Exception as e:
            return False, None, f"Неизвестная ошибка: {str(e)}"

    @staticmethod
    def get_available_formats(url: str) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        try:
            ydl_opts: Dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "socket_timeout": 30,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return False, [], "Не удалось получить информацию"
                
                entries = info.get("entries")
                if entries:
                    info = entries[0] if entries else info
                
                formats = info.get("formats") or []
                available: List[Dict[str, Any]] = []
                
                for f in formats:
                    format_id = f.get("format_id", "")
                    ext = f.get("ext", "")
                    quality = f.get("format_note") or f.get("quality", "")
                    height = f.get("height")
                    filesize = f.get("filesize") or f.get("filesize_approx", 0)
                    vcodec = f.get("vcodec", "none")
                    acodec = f.get("acodec", "none")
                    
                    if vcodec != "none" and acodec != "none":
                        type_str = "Видео+Аудио"
                    elif vcodec != "none":
                        type_str = "Только видео"
                    elif acodec != "none":
                        type_str = "Только аудио"
                    else:
                        type_str = "Другое"
                    
                    quality_label = f"{height}p" if height else str(quality)
                    
                    available.append({
                        "id": format_id,
                        "quality": f"{quality_label} ({ext})",
                        "type": type_str,
                        "size": filesize,
                        "ext": ext,
                        "height": height,
                    })
                
                return True, available, None
                
        except Exception as e:
            return False, [], str(e)
