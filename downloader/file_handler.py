import os
from pathlib import Path
from typing import Optional, Tuple
import mimetypes
import urllib.parse

from .models import FileCategory, VideoFormat


class FileTypeDetector:
    
    CONTENT_TYPE_MAP = {
        "video/mp4": (FileCategory.VIDEO, ".mp4", "Videos"),
        "video/webm": (FileCategory.VIDEO, ".webm", "Videos"),
        "video/x-matroska": (FileCategory.VIDEO, ".mkv", "Videos"),
        "video/avi": (FileCategory.VIDEO, ".avi", "Videos"),
        "video/quicktime": (FileCategory.VIDEO, ".mov", "Videos"),
        "video/x-msvideo": (FileCategory.VIDEO, ".avi", "Videos"),
        "video/x-ms-wmv": (FileCategory.VIDEO, ".wmv", "Videos"),
        "video/mpeg": (FileCategory.VIDEO, ".mpeg", "Videos"),
        "video/3gpp": (FileCategory.VIDEO, ".3gp", "Videos"),
        "video/x-flv": (FileCategory.VIDEO, ".flv", "Videos"),
        
        "audio/mpeg": (FileCategory.AUDIO, ".mp3", "Music"),
        "audio/mp3": (FileCategory.AUDIO, ".mp3", "Music"),
        "audio/wav": (FileCategory.AUDIO, ".wav", "Music"),
        "audio/wave": (FileCategory.AUDIO, ".wav", "Music"),
        "audio/x-wav": (FileCategory.AUDIO, ".wav", "Music"),
        "audio/flac": (FileCategory.AUDIO, ".flac", "Music"),
        "audio/ogg": (FileCategory.AUDIO, ".ogg", "Music"),
        "audio/aac": (FileCategory.AUDIO, ".aac", "Music"),
        "audio/m4a": (FileCategory.AUDIO, ".m4a", "Music"),
        "audio/x-m4a": (FileCategory.AUDIO, ".m4a", "Music"),
        "audio/webm": (FileCategory.AUDIO, ".webm", "Music"),
        "audio/x-wav": (FileCategory.AUDIO, ".wav", "Music"),
        
        "image/jpeg": (FileCategory.IMAGE, ".jpg", "Images"),
        "image/jpg": (FileCategory.IMAGE, ".jpg", "Images"),
        "image/png": (FileCategory.IMAGE, ".png", "Images"),
        "image/gif": (FileCategory.IMAGE, ".gif", "Images"),
        "image/webp": (FileCategory.IMAGE, ".webp", "Images"),
        "image/bmp": (FileCategory.IMAGE, ".bmp", "Images"),
        "image/svg+xml": (FileCategory.IMAGE, ".svg", "Images"),
        "image/tiff": (FileCategory.IMAGE, ".tiff", "Images"),
        
        "application/pdf": (FileCategory.DOCUMENT, ".pdf", "Documents"),
        "application/msword": (FileCategory.DOCUMENT, ".doc", "Documents"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (FileCategory.DOCUMENT, ".docx", "Documents"),
        "application/vnd.ms-excel": (FileCategory.DOCUMENT, ".xls", "Documents"),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (FileCategory.DOCUMENT, ".xlsx", "Documents"),
        "application/vnd.ms-powerpoint": (FileCategory.DOCUMENT, ".ppt", "Documents"),
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": (FileCategory.DOCUMENT, ".pptx", "Documents"),
        "application/json": (FileCategory.DOCUMENT, ".json", "Documents"),
        "text/plain": (FileCategory.DOCUMENT, ".txt", "Documents"),
        "text/html": (FileCategory.DOCUMENT, ".html", "Documents"),
        "text/css": (FileCategory.DOCUMENT, ".css", "Documents"),
        "text/javascript": (FileCategory.DOCUMENT, ".js", "Documents"),
        "application/xml": (FileCategory.DOCUMENT, ".xml", "Documents"),
        
        "application/zip": (FileCategory.ARCHIVE, ".zip", "Archives"),
        "application/x-rar-compressed": (FileCategory.ARCHIVE, ".rar", "Archives"),
        "application/x-7z-compressed": (FileCategory.ARCHIVE, ".7z", "Archives"),
        "application/x-tar": (FileCategory.ARCHIVE, ".tar", "Archives"),
        "application/gzip": (FileCategory.ARCHIVE, ".gz", "Archives"),
        "application/x-bzip2": (FileCategory.ARCHIVE, ".bz2", "Archives"),
        "application/xz": (FileCategory.ARCHIVE, ".xz", "Archives"),
        "application/java-archive": (FileCategory.ARCHIVE, ".jar", "Archives"),
        
        "application/octet-stream": (FileCategory.APPLICATION, ".bin", "Applications"),
        "application/x-msdownload": (FileCategory.APPLICATION, ".exe", "Applications"),
        "application/x-shockwave-flash": (FileCategory.APPLICATION, ".swf", "Applications"),
        "application/x-silverlight": (FileCategory.APPLICATION, ".xap", "Applications"),
    }
    
    EXTENSION_MAP = {
        ".mp4": (FileCategory.VIDEO, "video/mp4"),
        ".webm": (FileCategory.VIDEO, "video/webm"),
        ".mkv": (FileCategory.VIDEO, "video/x-matroska"),
        ".avi": (FileCategory.VIDEO, "video/x-msvideo"),
        ".mov": (FileCategory.VIDEO, "video/quicktime"),
        ".wmv": (FileCategory.VIDEO, "video/x-ms-wmv"),
        ".flv": (FileCategory.VIDEO, "video/x-flv"),
        ".m4v": (FileCategory.VIDEO, "video/x-m4v"),
        ".3gp": (FileCategory.VIDEO, "video/3gpp"),
        ".mpeg": (FileCategory.VIDEO, "video/mpeg"),
        ".mpg": (FileCategory.VIDEO, "video/mpeg"),
        
        ".mp3": (FileCategory.AUDIO, "audio/mpeg"),
        ".wav": (FileCategory.AUDIO, "audio/wav"),
        ".flac": (FileCategory.AUDIO, "audio/flac"),
        ".ogg": (FileCategory.AUDIO, "audio/ogg"),
        ".aac": (FileCategory.AUDIO, "audio/aac"),
        ".m4a": (FileCategory.AUDIO, "audio/mp4"),
        ".opus": (FileCategory.AUDIO, "audio/opus"),
        ".wma": (FileCategory.AUDIO, "audio/x-ms-wma"),
        ".ape": (FileCategory.AUDIO, "audio/x-ape"),
        
        ".jpg": (FileCategory.IMAGE, "image/jpeg"),
        ".jpeg": (FileCategory.IMAGE, "image/jpeg"),
        ".png": (FileCategory.IMAGE, "image/png"),
        ".gif": (FileCategory.IMAGE, "image/gif"),
        ".webp": (FileCategory.IMAGE, "image/webp"),
        ".bmp": (FileCategory.IMAGE, "image/bmp"),
        ".svg": (FileCategory.IMAGE, "image/svg+xml"),
        ".tiff": (FileCategory.IMAGE, "image/tiff"),
        ".tif": (FileCategory.IMAGE, "image/tiff"),
        ".ico": (FileCategory.IMAGE, "image/x-icon"),
        ".psd": (FileCategory.IMAGE, "image/vnd.adobe.photoshop"),
        
        ".pdf": (FileCategory.DOCUMENT, "application/pdf"),
        ".doc": (FileCategory.DOCUMENT, "application/msword"),
        ".docx": (FileCategory.DOCUMENT, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ".xls": (FileCategory.DOCUMENT, "application/vnd.ms-excel"),
        ".xlsx": (FileCategory.DOCUMENT, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ".ppt": (FileCategory.DOCUMENT, "application/vnd.ms-powerpoint"),
        ".pptx": (FileCategory.DOCUMENT, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ".txt": (FileCategory.DOCUMENT, "text/plain"),
        ".html": (FileCategory.DOCUMENT, "text/html"),
        ".htm": (FileCategory.DOCUMENT, "text/html"),
        ".css": (FileCategory.DOCUMENT, "text/css"),
        ".js": (FileCategory.DOCUMENT, "text/javascript"),
        ".json": (FileCategory.DOCUMENT, "application/json"),
        ".xml": (FileCategory.DOCUMENT, "application/xml"),
        ".csv": (FileCategory.DOCUMENT, "text/csv"),
        ".rtf": (FileCategory.DOCUMENT, "application/rtf"),
        ".epub": (FileCategory.DOCUMENT, "application/epub+zip"),
        
        ".zip": (FileCategory.ARCHIVE, "application/zip"),
        ".rar": (FileCategory.ARCHIVE, "application/x-rar-compressed"),
        ".7z": (FileCategory.ARCHIVE, "application/x-7z-compressed"),
        ".tar": (FileCategory.ARCHIVE, "application/x-tar"),
        ".gz": (FileCategory.ARCHIVE, "application/gzip"),
        ".bz2": (FileCategory.ARCHIVE, "application/x-bzip2"),
        ".xz": (FileCategory.ARCHIVE, "application/xz"),
        ".jar": (FileCategory.ARCHIVE, "application/java-archive"),
        
        ".exe": (FileCategory.APPLICATION, "application/x-msdownload"),
        ".msi": (FileCategory.APPLICATION, "application/x-msi"),
        ".dmg": (FileCategory.APPLICATION, "application/x-apple-diskimage"),
        ".deb": (FileCategory.APPLICATION, "application/x-debian-package"),
        ".rpm": (FileCategory.APPLICATION, "application/x-rpm"),
        ".apk": (FileCategory.APPLICATION, "application/vnd.android.package-archive"),
        ".bin": (FileCategory.APPLICATION, "application/octet-stream"),
    }
    
    @classmethod
    def detect_from_url(cls, url: str) -> Tuple[FileCategory, str, str]:
        try:
            parsed = urllib.parse.urlparse(url)
            path = parsed.path.lower()
            
            ext = os.path.splitext(path)[1] if path else ""
            if ext and ext in cls.EXTENSION_MAP:
                category, mime = cls.EXTENSION_MAP[ext]
                folder = cls._get_folder_for_category(category)
                return category, ext, folder
            
            filename = os.path.basename(path)
            if filename:
                ext = os.path.splitext(filename)[1].lower()
                if ext and ext in cls.EXTENSION_MAP:
                    category, mime = cls.EXTENSION_MAP[ext]
                    folder = cls._get_folder_for_category(category)
                    return category, ext, folder
            
            return FileCategory.OTHER, "", "Downloads"
            
        except Exception:
            return FileCategory.OTHER, "", "Downloads"
    
    @classmethod
    def detect_from_content_type(cls, content_type: str) -> Tuple[FileCategory, str, str]:
        if not content_type:
            return FileCategory.OTHER, "", "Downloads"
        
        content_type = content_type.lower().strip()
        
        if content_type in cls.CONTENT_TYPE_MAP:
            category, ext, folder = cls.CONTENT_TYPE_MAP[content_type]
            return category, ext, folder
        
        base_type = content_type.split(";")[0].strip()
        if base_type in cls.CONTENT_TYPE_MAP:
            category, ext, folder = cls.CONTENT_TYPE_MAP[base_type]
            return category, ext, folder
        
        if base_type.startswith("video/"):
            return FileCategory.VIDEO, ".video", "Videos"
        elif base_type.startswith("audio/"):
            return FileCategory.AUDIO, ".audio", "Music"
        elif base_type.startswith("image/"):
            return FileCategory.IMAGE, ".image", "Images"
        elif base_type.startswith("text/"):
            return FileCategory.DOCUMENT, ".txt", "Documents"
        elif base_type.startswith("application/"):
            return FileCategory.APPLICATION, ".bin", "Applications"
        
        return FileCategory.OTHER, "", "Downloads"
    
    @classmethod
    def detect_from_extension(cls, extension: str) -> Tuple[FileCategory, str]:
        if not extension:
            return FileCategory.OTHER, ""
        
        ext = extension.lower()
        if not ext.startswith("."):
            ext = "." + ext
        
        if ext in cls.EXTENSION_MAP:
            category, mime = cls.EXTENSION_MAP[ext]
            return category, mime
        
        return FileCategory.OTHER, ""
    
    @classmethod
    def _get_folder_for_category(cls, category: FileCategory) -> str:
        folders = {
            FileCategory.VIDEO: "Videos",
            FileCategory.AUDIO: "Music",
            FileCategory.IMAGE: "Images",
            FileCategory.DOCUMENT: "Documents",
            FileCategory.ARCHIVE: "Archives",
            FileCategory.APPLICATION: "Applications",
            FileCategory.OTHER: "Downloads",
        }
        return folders.get(category, "Downloads")
    
    @classmethod
    def get_category_folder(cls, category: FileCategory) -> str:
        return cls._get_folder_for_category(category)


class FolderManager:
    def __init__(self, base_path: Optional[str] = None):
        self._base_path = Path(base_path) if base_path else Path.home() / "Downloads"
        self._base_path.mkdir(parents=True, exist_ok=True)
        
        self._category_folders: dict[FileCategory, Path] = {}
        self._setup_category_folders()
    
    def _setup_category_folders(self):
        categories = [
            FileCategory.VIDEO,
            FileCategory.AUDIO,
            FileCategory.IMAGE,
            FileCategory.DOCUMENT,
            FileCategory.ARCHIVE,
            FileCategory.APPLICATION,
            FileCategory.OTHER,
        ]
        
        for category in categories:
            folder_name = FileTypeDetector.get_category_folder(category)
            folder_path = self._base_path / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)
            self._category_folders[category] = folder_path
    
    def get_folder(self, category: FileCategory) -> Path:
        return self._category_folders.get(category, self._base_path)
    
    def get_folder_for_url(self, url: str) -> Path:
        category, _, _ = FileTypeDetector.detect_from_url(url)
        return self.get_folder(category)
    
    def set_base_path(self, path: str):
        self._base_path = Path(path)
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._setup_category_folders()
    
    def get_all_folders(self) -> dict[FileCategory, Path]:
        return self._category_folders.copy()
    
    @property
    def base_path(self) -> Path:
        return self._base_path
