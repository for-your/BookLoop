"""
零依赖后台定时任务：启动一个守护线程，周期性执行维护扫描。
使用标准库线程，不额外引入 APScheduler；生产多实例可改为外部 cron 或分布式调度。
"""
from __future__ import annotations

import logging
import threading

from ..db import SessionLocal
from . import maintenance

logger = logging.getLogger("campus.scheduler")

_stop = threading.Event()
_thread: threading.Thread | None = None


def _loop(interval: int) -> None:
    # 启动即先跑一轮，之后每 interval 秒一轮
    while not _stop.is_set():
        try:
            db = SessionLocal()
            try:
                result = maintenance.run_all(db)
                if any(result.values()):
                    logger.info("维护扫描完成：%s", result)
            finally:
                db.close()
        except Exception as e:  # 任一轮失败不影响后续轮次
            logger.exception("维护扫描异常：%s", e)
        _stop.wait(interval)


def start(interval: int = 60) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(interval,), daemon=True, name="maintenance-scheduler")
    _thread.start()


def stop() -> None:
    _stop.set()
