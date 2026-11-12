"""
模块八：后台管理与统计模块
内容审核、用户管理、捐赠回收、统计分析（月报/季报/学期报导出）、操作日志、参数配置。
"""
from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.config import CONDITION_LEVELS
from ..core.deps import get_admin, get_current_user
from ..core.response import BizError, ok
from ..core.security import decrypt_field, mask_phone
from ..db import get_db
from ..models import (
    Book,
    Donation,
    HandoffPoint,
    Listing,
    OperationLog,
    Order,
    Report,
    User,
)
from ..schemas import DonationIn, ParamIn
from ..services import credit, notify, params
from ..services.batch import load_map
from ..services.log import write_log

router = APIRouter(prefix="/admin", tags=["后台管理与统计"])


# ---------------- 内容审核 ----------------
@router.get("/pending", summary="待审核内容聚合")
def pending(db: Session = Depends(get_db), user: User = Depends(get_admin)):
    books = db.query(Book).filter(Book.audit_status == "pending").all()
    reports = db.query(Report).filter(Report.status == "pending").all()
    return ok(
        {
            "books": [{"id": b.id, "isbn": b.isbn, "title": b.title, "author": b.author, "cover": b.cover} for b in books],
            "reports": [
                {"id": r.id, "target_type": r.target_type, "target_id": r.target_id,
                 "reason_type": r.reason_type, "detail": r.detail, "created_at": r.created_at.isoformat()}
                for r in reports
            ],
        }
    )


@router.post("/reports/{report_id}/handle")
def handle_report(report_id: int, result: str = "已处理", ban: bool = False, request: Request = None,
                  db: Session = Depends(get_db), user: User = Depends(get_admin)):
    r = db.get(Report, report_id)
    if not r:
        raise BizError("举报不存在", 404)
    r.status = "handled"
    r.handle_result = result
    r.handler_id = user.id
    if ban and r.target_type == "listing":
        l = db.get(Listing, r.target_id)
        if l:
            l.status = "banned"
    db.commit()
    write_log(db, user.id, "report_handle", f"report:{report_id}", after=result, request=request)
    return ok(True, "处理完成")


# ---------------- 用户管理 ----------------
@router.get("/users")
def users(keyword: str = "", role: str = "", status: str = "", page: int = 1, size: int = 20,
          db: Session = Depends(get_db), user: User = Depends(get_admin)):
    q = db.query(User)
    if keyword:
        q = q.filter(User.name.like(f"%{keyword}%") | User.college.like(f"%{keyword}%"))
    if role:
        q = q.filter(User.role == role)
    if status:
        q = q.filter(User.status == status)
    total = q.count()
    rows = q.order_by(User.id.desc()).offset((page - 1) * size).limit(size).all()
    return ok(
        {
            "total": total,
            "items": [
                {"id": u.id, "name": u.name, "student_no": mask_phone(decrypt_field(u.student_no)) if False else decrypt_field(u.student_no),
                 "phone": mask_phone(decrypt_field(u.phone)), "college": u.college, "role": u.role,
                 "credit_score": u.credit_score, "level": credit.level_of(u.credit_score),
                 "status": u.status, "created_at": u.created_at.isoformat()}
                for u in rows
            ],
        }
    )


@router.post("/users/{user_id}/status")
def set_status(user_id: int, status: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    u = db.get(User, user_id)
    if not u:
        raise BizError("用户不存在", 404)
    before = u.status
    u.status = status
    db.commit()
    write_log(db, user.id, "user_status", f"user:{user_id}", before=before, after=status, request=request)
    return ok(True, f"已{'禁用' if status != 'active' else '启用'}账号")


@router.post("/users/{user_id}/credit")
def adjust_credit(user_id: int, delta: int, reason: str = "管理员人工调整", request: Request = None,
                  db: Session = Depends(get_db), user: User = Depends(get_admin)):
    u = db.get(User, user_id)
    if not u:
        raise BizError("用户不存在", 404)
    before = u.credit_score
    new_score = credit.change_credit(db, user_id, delta, "manual", "user", user_id)
    notify.notify(db, user_id, "信用分调整", f"管理员调整信用分 {delta}（{reason}），当前 {new_score} 分", type="credit")
    db.commit()
    write_log(db, user.id, "credit_adjust", f"user:{user_id}", before=str(before), after=f"{new_score}/{reason}", request=request)
    return ok({"score": new_score}, "调整完成并留痕")


# ---------------- 捐赠回收 ----------------
@router.post("/donations", summary="学生主动捐赠教材")
def create_donation(body: DonationIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    book = db.get(Book, body.book_id) if body.book_id else db.query(Book).filter(Book.isbn == body.isbn).first()
    if not book:
        raise BizError("请选择教材", 404)
    d = Donation(user_id=user.id, book_id=book.id, quantity=body.quantity, status="pending")
    db.add(d)
    db.commit()
    return ok({"id": d.id}, "捐赠申请已提交，等待学工部审核")


@router.get("/donations")
def donations(status: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Donation)
    if user.role != "admin":
        q = q.filter(Donation.user_id == user.id)
    if status:
        q = q.filter(Donation.status == status)
    rows = q.order_by(Donation.id.desc()).limit(100).all()
    books = load_map(db, Book, (d.book_id for d in rows))
    users = load_map(db, User, (d.user_id for d in rows))
    out = []
    for d in rows:
        b = books.get(d.book_id)
        u = users.get(d.user_id)
        out.append({"id": d.id, "book_title": b.title if b else "", "user": (u.nickname or u.name) if u else "",
                    "quantity": d.quantity, "status": d.status, "beneficiary": d.beneficiary,
                    "created_at": d.created_at.isoformat()})
    return ok(out)


@router.post("/donations/{donation_id}/approve", summary="学工部审核并赠予困难学生")
def approve_donation(donation_id: int, beneficiary: str = "", request: Request = None,
                     db: Session = Depends(get_db), user: User = Depends(get_admin)):
    d = db.get(Donation, donation_id)
    if not d:
        raise BizError("捐赠记录不存在", 404)
    d.status = "approved"
    d.beneficiary = beneficiary or "待分配"
    notify.notify(db, d.user_id, "捐赠审核通过", f"你的捐赠已审核通过，受赠人：{d.beneficiary}", type="system")
    db.commit()
    write_log(db, user.id, "donation_approve", f"donation:{donation_id}", after=d.beneficiary, request=request)
    return ok(True, "审核通过")


# ---------------- 统计分析 ----------------
@router.get("/stats/overview", summary="统计总览：复用率、节约金额、成交排行、热门教材、交接点负载")
def stats(db: Session = Depends(get_db), user: User = Depends(get_admin)):
    completed = db.query(Order).filter(Order.status == "completed").all()
    on_sale = db.query(Listing).filter(Listing.status == "on_sale").count()
    total_listings = db.query(Listing).count()
    deal_cnt = len(completed)

    # 批量加载关联实体（避免逐订单 N+1）
    listings = load_map(db, Listing, (o.listing_id for o in completed))
    books = load_map(db, Book, (l.book_id for l in listings.values()))
    buyers = load_map(db, User, (o.buyer_id for o in completed))
    points = load_map(db, HandoffPoint, (o.point_id for o in completed))

    saved = 0.0
    for o in completed:
        l = listings.get(o.listing_id)
        b = books.get(l.book_id) if l else None
        if b:
            saved += max(0.0, b.price - o.price)

    reuse_rate = round(deal_cnt / (deal_cnt + on_sale) * 100, 2) if (deal_cnt + on_sale) else 0.0

    # 学院成交排行
    college_rank: dict[str, int] = {}
    for o in completed:
        u = buyers.get(o.buyer_id)
        if u:
            college_rank[u.college or "未填写"] = college_rank.get(u.college or "未填写", 0) + 1

    # 热门教材 TOP20
    hot: dict[int, int] = {}
    for o in completed:
        l = listings.get(o.listing_id)
        if l:
            hot[l.book_id] = hot.get(l.book_id, 0) + 1
    hot_list = sorted(hot.items(), key=lambda x: -x[1])[:20]
    hot_out = []
    for bid, cnt in hot_list:
        b = books.get(bid)
        if b:
            hot_out.append({"book_id": bid, "title": b.title, "isbn": b.isbn, "deal_count": cnt})

    # 交接点负载
    point_load: dict[int, int] = {}
    for o in completed:
        if o.point_id:
            point_load[o.point_id] = point_load.get(o.point_id, 0) + 1
    points_out = []
    for pid, cnt in point_load.items():
        p = points.get(pid)
        if p:
            points_out.append({"point_id": pid, "name": p.name, "deal_count": cnt, "capacity": p.capacity,
                               "load_rate": round(cnt / max(1, p.capacity) * 100, 1)})

    return ok(
        {
            "users": db.query(User).count(),
            "books": db.query(Book).count(),
            "listings": total_listings,
            "on_sale": on_sale,
            "deals": deal_cnt,
            "reuse_rate": reuse_rate,
            "saved_amount": round(saved, 2),
            "college_rank": sorted(
                [{"college": k, "count": v} for k, v in college_rank.items()], key=lambda x: -x["count"]
            ),
            "hot_books": hot_out,
            "point_load": points_out,
        }
    )


@router.get("/stats/export", summary="报表导出（月报/季报/学期报，Excel）")
def export_report(period: str = "month", db: Session = Depends(get_db), user: User = Depends(get_admin)):
    from openpyxl import Workbook

    data = stats(db=db, user=user)["data"]
    wb = Workbook()
    ws = wb.active
    ws.title = "统计报表"
    ws.append(["指标", "数值"])
    ws.append(["注册用户数", data["users"]])
    ws.append(["教材目录条目", data["books"]])
    ws.append(["累计挂牌", data["listings"]])
    ws.append(["在架挂牌", data["on_sale"]])
    ws.append(["成交笔数", data["deals"]])
    ws.append(["教材复用率(%)", data["reuse_rate"]])
    ws.append(["累计节约金额(元)", data["saved_amount"]])

    ws.append([])
    ws.append(["学院", "成交笔数"])
    for r in data["college_rank"]:
        ws.append([r["college"], r["count"]])

    ws.append([])
    ws.append(["热门教材", "书籍编号", "成交笔数"])
    for r in data["hot_books"]:
        ws.append([r["title"], r["isbn"], r["deal_count"]])

    ws.append([])
    ws.append(["交接点", "成交笔数", "负载率(%)"])
    for r in data["point_load"]:
        ws.append([r["name"], r["deal_count"], r["load_rate"]])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    name = {"month": "月报", "quarter": "季报", "term": "学期报"}.get(period, "月报")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=report_{period}.xlsx"},
    )


# ---------------- 操作日志 ----------------
@router.get("/logs")
def logs(action: str = "", page: int = 1, size: int = 50, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    q = db.query(OperationLog)
    if action:
        q = q.filter(OperationLog.action == action)
    total = q.count()
    rows = q.order_by(OperationLog.id.desc()).offset((page - 1) * size).limit(size).all()
    return ok(
        {
            "total": total,
            "items": [
                {"id": r.id, "operator_id": r.operator_id, "action": r.action, "target": r.target,
                 "before": r.before, "after": r.after, "ip": r.ip, "created_at": r.created_at.isoformat()}
                for r in rows
            ],
        }
    )


# ---------------- 参数配置 ----------------
@router.get("/params")
def get_params(db: Session = Depends(get_db), user: User = Depends(get_admin)):
    return ok(params.all_params(db))


@router.put("/params", summary="修改业务参数（禁止硬编码）")
def set_params(body: ParamIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    old = params.get_param(db, body.key)
    params.set_param(db, body.key, body.value, body.remark)
    write_log(db, user.id, "param_update", f"param:{body.key}", before=str(old), after=body.value, request=request)
    return ok({"key": body.key, "value": body.value}, "参数已更新并生效")


@router.get("/conditions")
def conditions():
    return ok(CONDITION_LEVELS)
