import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Optional
from logging.handlers import RotatingFileHandler
import traceback


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class Logger:
    _instances = {}
    
    def __new__(cls, name: str = "ytDownloader", 
                 log_dir: Optional[str] = None,
                 max_bytes: int = 10 * 1024 * 1024,
                 backup_count: int = 5):
        
        if name in cls._instances:
            return cls._instances[name]
        
        instance = super().__new__(cls)
        cls._instances[name] = instance
        instance._initialized = False
        return instance
    
    def __init__(self, name: str = "ytDownloader",
                 log_dir: Optional[str] = None,
                 max_bytes: int = 10 * 1024 * 1024,
                 backup_count: int = 5):
        
        if self._initialized:
            return
        
        self._initialized = True
        self._name = name
        self._log_dir = Path(log_dir) if log_dir else Path.home() / ".ytDownloader" / "logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers = []
        
        log_file = self._log_dir / f"{name}.log"
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        
        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)
        
        self._gui_callbacks = []
    
    def set_level(self, level: LogLevel):
        self._logger.setLevel(level.value)
        for handler in self._logger.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                if level == LogLevel.DEBUG:
                    handler.setLevel(logging.DEBUG)
                else:
                    handler.setLevel(logging.INFO)
    
    def add_gui_callback(self, callback):
        self._gui_callbacks.append(callback)
    
    def remove_gui_callback(self, callback):
        if callback in self._gui_callbacks:
            self._gui_callbacks.remove(callback)
    
    def _emit_to_gui(self, level: str, message: str, exc_info: Optional[Exception] = None):
        for callback in self._gui_callbacks:
            try:
                callback(level, message, exc_info)
            except Exception:
                pass
    
    def debug(self, message: str, exc_info: bool = False):
        self._logger.debug(message, exc_info=exc_info)
    
    def info(self, message: str):
        self._logger.info(message)
        self._emit_to_gui("INFO", message)
    
    def warning(self, message: str):
        self._logger.warning(message)
        self._emit_to_gui("WARNING", message)
    
    def error(self, message: str, exc_info: Optional[Exception] = None):
        if exc_info:
            self._logger.error(f"{message}: {exc_info}", exc_info=True)
            self._emit_to_gui("ERROR", f"{message}: {exc_info}", exc_info)
        else:
            self._logger.error(message)
            self._emit_to_gui("ERROR", message)
    
    def critical(self, message: str, exc_info: Optional[Exception] = None):
        if exc_info:
            self._logger.critical(f"{message}: {exc_info}", exc_info=True)
            self._emit_to_gui("CRITICAL", f"{message}: {exc_info}", exc_info)
        else:
            self._logger.critical(message)
            self._emit_to_gui("CRITICAL", message)
    
    def exception(self, message: str, exc: Optional[Exception] = None):
        exc_info = exc or sys.exc_info()
        self._logger.exception(message, exc_info=exc_info)
        self._emit_to_gui("ERROR", f"{message}: {exc_info[1] if exc_info else None}", exc_info[1] if exc_info else None)
    
    @property
    def log_file(self) -> Path:
        return self._log_dir / f"{self._name}.log"
    
    @property
    def log_dir(self) -> Path:
        return self._log_dir


class ErrorHandler:
    ERRORS = {
        "ConnectionError": {
            "message": "Ошибка подключения к серверу",
            "action": "Проверьте интернет-соединение"
        },
        "Timeout": {
            "message": "Превышен таймаут запроса",
            "action": "Попробуйте позже или используйте VPN"
        },
        "HTTPError_404": {
            "message": "Файл не найден (404)",
            "action": "Проверьте правильность ссылки"
        },
        "HTTPError_403": {
            "message": "Доступ запрещён (403)",
            "action": "Возможно, требуется авторизация"
        },
        "HTTPError_503": {
            "message": "Сервер недоступен (503)",
            "action": "Попробуйте позже"
        },
        "DiskFull": {
            "message": "Недостаточно места на диске",
            "action": "Освободите место или выберите другую папку"
        },
        "OSError_28": {
            "message": "Недостаточно места на диске (OS Error 28)",
            "action": "Освободите место на диске"
        },
        "InvalidURL": {
            "message": "Некорректная ссылка",
            "action": "Проверьте формат URL"
        },
        "FileExistsError": {
            "message": "Файл уже существует",
            "action": "Удалите существующий файл или выберите другое имя"
        },
        "PermissionError": {
            "message": "Нет прав доступа",
            "action": "Выберите другую папку для сохранения"
        },
        "yt_dlp_error": {
            "message": "Ошибка загрузки видео",
            "action": "Проверьте ссылку или попробуйте другой формат"
        },
        "Unknown": {
            "message": "Неизвестная ошибка",
            "action": "Обратитесь к логам для диагностики"
        }
    }
    
    def __init__(self, logger: Optional[Logger] = None):
        self._logger = logger or Logger()
    
    def handle(self, error: Exception, context: str = "") -> dict:
        error_type = self._classify_error(error)
        error_info = self.ERRORS.get(error_type, self.ERRORS["Unknown"])
        
        user_message = f"{error_info['message']}"
        if context:
            user_message = f"{context}: {user_message}"
        
        user_action = error_info['action']
        
        self._logger.error(
            f"{error_type} in {context}: {error}",
            exc_info=error
        )
        
        return {
            "type": error_type,
            "message": user_message,
            "action": user_action,
            "details": str(error),
            "traceback": traceback.format_exc() if self._logger._logger.level == logging.DEBUG else None
        }
    
    def _classify_error(self, error: Exception) -> str:
        error_name = type(error).__name__
        
        if isinstance(error, ConnectionError):
            return "ConnectionError"
        
        if isinstance(error, TimeoutError):
            return "Timeout"
        
        if isinstance(error, OSError) and getattr(error, "errno", 0) == 28:
            return "OSError_28"
        
        if isinstance(error, PermissionError):
            return "PermissionError"
        
        if "yt_dlp" in str(error) or "ytdlp" in str(error).lower():
            return "yt_dlp_error"
        
        error_str = str(error).lower()
        
        if "404" in error_str or "not found" in error_str:
            return "HTTPError_404"
        if "403" in error_str or "forbidden" in error_str:
            return "HTTPError_403"
        if "503" in error_str or "unavailable" in error_str or "service unavailable" in error_str:
            return "HTTPError_503"
        
        if "disk full" in error_str or "no space left" in error_str:
            return "DiskFull"
        
        if "invalid url" in error_str or "unknown url type" in error_str:
            return "InvalidURL"
        
        if "file exists" in error_str:
            return "FileExistsError"
        
        return "Unknown"
    
    @classmethod
    def get_error_message(cls, error_type: str) -> tuple[str, str]:
        info = cls.ERRORS.get(error_type, cls.ERRORS["Unknown"])
        return info["message"], info["action"]


def get_logger(name: str = "ytDownloader", 
               log_dir: Optional[str] = None) -> Logger:
    return Logger(name=name, log_dir=log_dir)
