from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict


class Status(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"
    EXTRACTING = "extracting"
    PROCESSING = "processing"


class DownloadType(Enum):
    HTTP = "http"
    VIDEO = "video"


class FileCategory(Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    APPLICATION = "application"
    OTHER = "other"


class VideoFormat(Enum):
    BEST = "best"
    MP4 = "mp4"
    WEBM = "webm"
    MKV = "mkv"
    AVI = "avi"
    MP3 = "mp3"
    WAV = "wav"
    FLAC = "flac"
    M4A = "m4a"
    OPUS = "opus"


class VideoQuality(Enum):
    BEST = "best"
    QUALITY_4K = "2160"
    QUALITY_1440 = "1440"
    QUALITY_1080 = "1080"
    QUALITY_720 = "720"
    QUALITY_480 = "480"
    QUALITY_360 = "360"
    QUALITY_240 = "240"


@dataclass
class DownloadTask:
    id: str
    url: str
    dest_path: Path
    status: Status = Status.PENDING
    bytes_downloaded: int = 0
    total_bytes: int = 0
    speed_limit: int = 0
    error: Optional[str] = None
    created_at: float = 0
    resume_position: int = 0
    download_type: DownloadType = DownloadType.HTTP
    file_category: FileCategory = FileCategory.OTHER
    video_format: Optional[VideoFormat] = None
    video_quality: Optional[VideoQuality] = None
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    content_type: Optional[str] = None
    _ytdlp_info: Optional[Dict] = field(default=None, repr=False)


@dataclass
class VideoInfo:
    url: str
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    formats: List[Dict] = field(default_factory=list)
    is_playlist: bool = False
    playlist_count: int = 0
    uploader: Optional[str] = None
    description: Optional[str] = None
    upload_date: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
