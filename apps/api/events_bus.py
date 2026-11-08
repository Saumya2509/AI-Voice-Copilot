"""In-process publish and subscribe for live updates (new orders, data imports).

Publishers may run in worker threads (the PoS push runs in a threadpool); subscribers are asyncio
queues read by the server-sent events endpoint."""
from __future__ import annotations

import asyncio
import threading
from typing import Any

_lock = threading.Lock()
_subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    with _lock:
        _subscribers.append((asyncio.get_running_loop(), q))
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    with _lock:
        _subscribers[:] = [(lp, x) for lp, x in _subscribers if x is not q]


def publish(event: str, data: dict[str, Any]) -> None:
    with _lock:
        targets = list(_subscribers)
    for loop, q in targets:
        def put(q=q):
            if not q.full():
                q.put_nowait((event, data))
        try:
            loop.call_soon_threadsafe(put)
        except RuntimeError:  # loop closed
            unsubscribe(q)


def subscriber_count() -> int:
    with _lock:
        return len(_subscribers)
