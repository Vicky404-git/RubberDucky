"""Thread-safe in-process event bus for live frontend updates.

The session runner executes in a worker thread; FastAPI/WebSocket consumers
run on the asyncio loop. Events are always plain, redacted dictionaries.
"""
from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from typing import Any


class EventBus:
    def __init__(self, history_size: int = 200) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history)

    def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "type": event_type,
            "timestamp": time.time(),
            **(payload or {}),
        }
        with self._lock:
            self._history.append(event)
            subscribers = list(self._subscribers)
            loop = self._loop

        if loop is None or loop.is_closed():
            return event

        def _deliver() -> None:
            for queue in subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # Slow consumer: drop the oldest item, keep the stream live.
                    try:
                        queue.get_nowait()
                        queue.put_nowait(event)
                    except (asyncio.QueueEmpty, asyncio.QueueFull):
                        pass

        try:
            loop.call_soon_threadsafe(_deliver)
        except RuntimeError:
            pass
        return event

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.discard(queue)


event_bus = EventBus()
