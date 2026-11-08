"""Version counter for precomputed revenue tables. Anything that changes menu or order data
(CSV import, price apply) calls `invalidate()`; cached analytics rebuild on the next read."""
from __future__ import annotations

import threading

_lock = threading.Lock()
_version = 0
_listeners: list = []


def version() -> int:
    return _version


def on_invalidate(fn) -> None:
    _listeners.append(fn)


def invalidate() -> int:
    global _version
    with _lock:
        _version += 1
    for fn in list(_listeners):
        fn()
    return _version
