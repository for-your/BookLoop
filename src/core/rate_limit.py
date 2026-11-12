"""
内存滑动窗口限流：单进程部署足够；生产多实例可替换为 Redis 实现（见 services/notify.py 的 USE_REDIS）。
"""
from __future__ import annotations

import threading
import time

from fastapi import Request

_LOCK = threading.Lock()
_WINDOWS: dict[str, list[float]] = {}
_MAX_KEYS = 100_000  # 防止内存无限增长


def hit(key: str, max_calls: int, window_sec: int) -> bool:
    """记录一次访问。返回 True 表示放行，False 表示超限。"""
    now = time.time()
    with _LOCK:
        stamps = [t for t in _WINDOWS.get(key, []) if now - t < window_sec]
        if len(stamps) >= max_calls:
            _WINDOWS[key] = stamps
            return False
        stamps.append(now)
        _WINDOWS[key] = stamps
        _trim_locked(now)
        return True


def _trim_locked(now: float) -> None:
    if len(_WINDOWS) <= _MAX_KEYS:
        return
    for k in list(_WINDOWS.keys()):
        _WINDOWS[k] = [t for t in _WINDOWS[k] if now - t < 3600]
        if not _WINDOWS[k]:
            _WINDOWS.pop(k, None)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
