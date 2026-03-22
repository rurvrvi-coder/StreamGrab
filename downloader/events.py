from threading import Lock
from typing import Callable, Dict, List
from enum import Enum
from threading import Thread


class EventType(Enum):
    PROGRESS = "progress"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"
    RESUMED = "resumed"
    CANCELLED = "cancelled"
    ADDED = "added"


class EventEmitter:
    def __init__(self):
        self._listeners: Dict[EventType, List[Callable]] = {}
        self._lock = Lock()

    def on(self, event: EventType, callback: Callable) -> Callable:
        with self._lock:
            if event not in self._listeners:
                self._listeners[event] = []
            self._listeners[event].append(callback)
        return lambda: self.off(event, callback)

    def off(self, event: EventType, callback: Callable):
        with self._lock:
            if event in self._listeners:
                self._listeners[event].remove(callback)

    def emit(self, event: EventType, data: dict):
        def notify():
            with self._lock:
                callbacks = self._listeners.get(event, []).copy()
            for cb in callbacks:
                try:
                    cb(data)
                except Exception:
                    pass

        Thread(target=notify, daemon=True).start()
