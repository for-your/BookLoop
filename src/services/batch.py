"""
批量加载 ORM 实体：消除列表序列化中的 N+1 查询。
用法：先收集一组主键，一次性查询并返回 {id: entity} 映射，循环内直接查字典。
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session


def load_map(db: Session, model, ids: Iterable[int]) -> dict[int, object]:
    """按主键批量加载，返回 {id: entity}；ids 自动去空去重。"""
    clean = {i for i in ids if i is not None}
    if not clean:
        return {}
    rows = db.query(model).filter(model.id.in_(clean)).all()
    return {r.id: r for r in rows}
