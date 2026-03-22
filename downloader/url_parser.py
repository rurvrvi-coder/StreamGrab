import re
from typing import Tuple, Optional, List
from urllib.parse import urlparse
from .models import VideoFormat, VideoQuality, DownloadType


VIDEO_DOMAINS = {
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "www.youtube.com": "YouTube",
    "m.youtube.com": "YouTube",
    "music.youtube.com": "YouTube",
    "vk.com": "VK",
    "m.vk.com": "VK",
    "www.vk.com": "VK",
    "vkontakte.ru": "VK",
    "vimeo.com": "Vimeo",
    "www.vimeo.com": "Vimeo",
    "dailymotion.com": "Dailymotion",
    "www.dailymotion.com": "Dailymotion",
    "twitch.tv": "Twitch",
    "www.twitch.tv": "Twitch",
    "soundcloud.com": "SoundCloud",
    "www.soundcloud.com": "SoundCloud",
    "bandcamp.com": "Bandcamp",
    "www.bandcamp.com": "Bandcamp",
    "rutube.ru": "RuTube",
    "www.rutube.ru": "Rutube",
    "ok.ru": "OK",
    "www.ok.ru": "OK",
    "coub.com": "Coub",
    "www.coub.com": "Coub",
    "yandex.ru": "Yandex Video",
    "video.yandex.ru": "Yandex Video",
}


class URLParser:
    @staticmethod
    def is_supported_video(url: str) -> bool:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")
            return domain in VIDEO_DOMAINS
        except Exception:
            return False

    @staticmethod
    def get_platform_name(url: str) -> Optional[str]:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")
            return VIDEO_DOMAINS.get(domain)
        except Exception:
            return None

    @staticmethod
    def is_youtube_playlist(url: str) -> bool:
        patterns = [
            r"list=",
            r"playlist",
            r"watch\?.*list=",
        ]
        return any(re.search(p, url, re.IGNORECASE) for p in patterns)

    @staticmethod
    def is_youtube_shorts(url: str) -> bool:
        return "/shorts/" in url.lower()

    @staticmethod
    def get_download_type(url: str) -> DownloadType:
        return DownloadType.VIDEO if URLParser.is_supported_video(url) else DownloadType.HTTP

    @staticmethod
    def get_format_string(video_format: Optional[VideoFormat], 
                         video_quality: Optional[VideoQuality]) -> str:
        if not video_format or video_format == VideoFormat.BEST:
            return "best"
        
        format_str = video_format.value
        
        if video_quality and video_quality != VideoQuality.BEST:
            format_str = f"{video_quality.value}+{format_str}"
        
        return format_str

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
        filename = re.sub(invalid_chars, "_", filename)
        filename = filename[:200].strip(". ")
        return filename or "download"

    @staticmethod
    def is_valid_url(url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False
