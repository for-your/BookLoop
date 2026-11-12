"""
信用分服务：分数变动、等级计算、发布资格校验。
规则（需求）：初始 80；成交并完成 +2；好评 +1、差评 -3；违约 -5；申诉败诉 -10；上限 100。
等级：优秀 ≥90、良好 80-89、一般 60-79、受限 <60。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import CreditLog, User
from . import params

CREDIT_REASONS = {
    "deal": "成交并完成",
    "good_review": "获得好评",
    "bad_review": "获得差评",
    "break": "单方取消违约",
    "break_urgent": "临近交接受理内取消",
    "overtime": "订单超时未核销",
    "appeal_lose": "申诉败诉",
    "manual": "管理员人工调整",
    "register": "初始信用分",
}


def level_of(score: int) -> str:
    if score >= 90:
        return "优秀"
    if score >= 80:
        return "良好"
    if score >= 60:
        return "一般"
    return "受限"


def change_credit(
    db: Session,
    user_id: int,
    delta: int,
    reason: str,
    ref_type: str = "",
    ref_id: int | None = None,
) -> int:
    """调整信用分并留痕，返回调整后的分数"""
    user = db.get(User, user_id)
    if not user:
        return 0
    max_score = params.get_param(db, "credit_max", 100)
    new_score = max(0, min(max_score, user.credit_score + delta))
    user.credit_score = new_score
    db.add(
        CreditLog(
            user_id=user_id,
            delta=delta,
            score_after=new_score,
            reason=CREDIT_REASONS.get(reason, reason),
            ref_type=ref_type,
            ref_id=ref_id,
        )
    )
    db.flush()
    return new_score


def can_publish(db: Session, user: User) -> bool:
    return user.credit_score >= params.get_param(db, "credit_publish_min", 60)


def credit_detail(db: Session, user_id: int, limit: int = 50) -> list[dict]:
    rows = (
        db.query(CreditLog)
        .filter(CreditLog.user_id == user_id)
        .order_by(CreditLog.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "delta": r.delta,
            "score_after": r.score_after,
            "reason": r.reason,
            "ref_type": r.ref_type,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
