"""
系统参数服务：业务阈值一律从 sys_params 读取，禁止硬编码（扩展性需求）。
带 60s 内存缓存，避免高频查询；后台修改参数后自动失效。
"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from ..core.config import DEFAULT_PARAMS
from ..models import SysParam

_CACHE: dict[str, tuple[float, str]] = {}
_TTL = 60.0


def invalidate() -> None:
    _CACHE.clear()


def _get_raw(db: Session, key: str) -> str | None:
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    row = db.query(SysParam).filter(SysParam.param_key == key).first()
    if row:
        _CACHE[key] = (now, row.param_value)
        return row.param_value
    return DEFAULT_PARAMS.get(key)


def get_param(db: Session, key: str, default=None):
    raw = _get_raw(db, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    try:
        return float(raw)
    except (TypeError, ValueError):
        return raw


def set_param(db: Session, key: str, value: str, remark: str = "") -> None:
    row = db.query(SysParam).filter(SysParam.param_key == key).first()
    if row:
        row.param_value = str(value)
        if remark:
            row.remark = remark
    else:
        db.add(SysParam(param_key=key, param_value=str(value), remark=remark))
    db.commit()
    invalidate()


def all_params(db: Session) -> list[dict]:
    rows = db.query(SysParam).order_by(SysParam.id).all()
    return [
        {
            "key": r.param_key,
            "value": r.param_value,
            "remark": r.remark,
            "default": DEFAULT_PARAMS.get(r.param_key, ""),
        }
        for r in rows
    ]
