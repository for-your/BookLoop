"""
模块七：评价与信用体系模块
双向评价（描述相符/成色真实/履约及时）、信用分计算、信用公示、申诉复核。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.deps import get_admin, get_current_user
from ..core.response import BizError, ok
from ..db import get_db
from ..models import Appeal, Order, Review, User
from ..schemas import ReviewAppealIn, ReviewIn
from ..services import credit, notify, params
from ..services.batch import load_map
from ..services.log import write_log

router = APIRouter(prefix="/reviews", tags=["评价与信用体系"])


@router.post("", summary="双向评价（交易完成后 7 日内）")
def create_review(body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = db.get(Order, body.order_id)
    if not o:
        raise BizError("订单不存在", 404)
    if user.id not in (o.buyer_id, o.seller_id):
        raise BizError("无权评价该订单", 403)
    if o.status != "completed":
        raise BizError("交易完成后方可评价")
    if o.completed_at and (datetime.utcnow() - o.completed_at) > timedelta(days=7):
        raise BizError("超过 7 日评价期")
    if db.query(Review).filter(Review.order_id == o.id, Review.reviewer_id == user.id).first():
        raise BizError("你已评价过该订单")

    target_id = o.seller_id if user.id == o.buyer_id else o.buyer_id
    r = Review(
        order_id=o.id,
        reviewer_id=user.id,
        target_id=target_id,
        rating_desc=body.rating_desc,
        rating_condition=body.rating_condition,
        rating_punctual=body.rating_punctual,
        comment=body.comment,
    )
    db.add(r)
    db.flush()

    avg = (body.rating_desc + body.rating_condition + body.rating_punctual) / 3
    if avg >= 4:
        delta = params.get_param(db, "credit_good_add", 1)
        credit.change_credit(db, target_id, delta, "good_review", "review", r.id)
        tip = f"好评，对方信用分 +{delta}"
    elif avg <= 2:
        delta = -params.get_param(db, "credit_bad_sub", 3)
        credit.change_credit(db, target_id, delta, "bad_review", "review", r.id)
        tip = f"差评，对方信用分 {delta}"
    else:
        tip = "中评，信用分不变"
    notify.notify(db, target_id, "收到新评价", f"订单评价：{tip}", type="credit", ref_id=r.id)
    db.commit()
    return ok({"id": r.id, "avg": round(avg, 2), "credit_effect": tip}, "评价已提交")


@router.get("/user/{user_id}", summary="信用公示：信用分、等级、历史评价")
def user_reviews(user_id: int, db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise BizError("用户不存在", 404)
    rows = db.query(Review).filter(Review.target_id == user_id).order_by(Review.id.desc()).limit(50).all()
    agg = db.query(
        func.avg(Review.rating_desc), func.avg(Review.rating_condition), func.avg(Review.rating_punctual), func.count(Review.id)
    ).filter(Review.target_id == user_id).first()
    return ok({
        "user_id": user_id,
        "nickname": u.nickname or u.name,
        "credit_score": u.credit_score,
        "credit_level": credit.level_of(u.credit_score),
        "avg_desc": round(agg[0] or 0, 2),
        "avg_condition": round(agg[1] or 0, 2),
        "avg_punctual": round(agg[2] or 0, 2),
        "count": agg[3] or 0,
        "items": [
            {"id": r.id, "rating_desc": r.rating_desc, "rating_condition": r.rating_condition,
             "rating_punctual": r.rating_punctual, "comment": r.comment, "created_at": r.created_at.isoformat()}
            for r in rows
        ],
    })


@router.get("/order/{order_id}")
def order_reviews(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Review).filter(Review.order_id == order_id).all()
    return ok([
        {"id": r.id, "reviewer_id": r.reviewer_id, "target_id": r.target_id,
         "rating_desc": r.rating_desc, "rating_condition": r.rating_condition,
         "rating_punctual": r.rating_punctual, "comment": r.comment,
         "created_at": r.created_at.isoformat()}
        for r in rows
    ])


# ---------------- 申诉 ----------------
@router.get("/appeals", summary="申诉列表")
def appeals(status: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Appeal)
    if user.role != "admin":
        q = q.filter(Appeal.applicant_id == user.id)
    if status:
        q = q.filter(Appeal.status == status)
    rows = q.order_by(Appeal.id.desc()).limit(100).all()
    applicants = load_map(db, User, (a.applicant_id for a in rows))
    return ok([
        {"id": a.id, "order_id": a.order_id, "applicant_id": a.applicant_id,
         "applicant": (lambda u: (u.nickname or u.name) if u else "")(applicants.get(a.applicant_id)),
         "reason_type": a.reason_type, "detail": a.detail, "status": a.status,
         "result": a.result, "credit_adjust": a.credit_adjust, "created_at": a.created_at.isoformat()}
        for a in rows
    ])


@router.post("/appeals/{appeal_id}/judge", summary="申诉复核裁定（管理员）")
def judge(appeal_id: int, body: ReviewAppealIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    a = db.get(Appeal, appeal_id)
    if not a:
        raise BizError("申诉不存在", 404)
    if a.status != "pending":
        raise BizError("该申诉已裁定")
    a.status = body.status
    a.result = body.result
    a.credit_adjust = body.credit_adjust

    o = db.get(Order, a.order_id)
    loser = a.applicant_id if body.status == "lose" else (
        o.seller_id if a.applicant_id == o.buyer_id else o.buyer_id
    )
    if body.status == "lose":
        sub = params.get_param(db, "credit_appeal_lose_sub", 10)
        credit.change_credit(db, a.applicant_id, -sub, "appeal_lose", "appeal", a.id)
        tip = f"申诉败诉，信用分 -{sub}"
    else:
        credit.change_credit(db, loser, -abs(body.credit_adjust or 0), "manual", "appeal", a.id) if body.credit_adjust else None
        tip = "申诉成立"
    if o:
        o.status = "completed"
    notify.notify(db, a.applicant_id, "申诉裁定结果", f"你的申诉已裁定：{tip}。{body.result}", type="credit", ref_id=a.id)
    db.commit()
    write_log(db, user.id, "appeal_judge", f"appeal:{appeal_id}", after=body.status, request=request)
    return ok({"id": a.id, "status": a.status}, "裁定完成")
