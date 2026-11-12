"""
模块六：线下交接点管理模块
交接点维护、30 分钟时段预约（单时段容量上限）、扫码/核销码核销、
异常登记、暂存 7 日超期转捐赠回收池。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..core.deps import get_admin, get_current_user, get_point_admin
from ..core.response import BizError, ok
from ..core.security import decrypt_field
from ..db import get_db
from ..models import (
    Book,
    HandoffPoint,
    HandoffSlot,
    Listing,
    Order,
    OrderEvent,
    StorageItem,
    User,
)
from ..schemas import MyPointIn, PointAdminCertIn, PointIn
from ..services import maintenance, notify, params
from ..services.batch import load_map
from ..services.log import write_log

router = APIRouter(prefix="/handoff", tags=["线下交接点管理"])


def _point_out(db: Session, p: HandoffPoint, user: User | None = None,
               today_used: int | None = None, today_cap: int | None = None) -> dict:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if today_used is None or today_cap is None:
        today_used = db.query(func.sum(HandoffSlot.used)).filter(HandoffSlot.point_id == p.id, HandoffSlot.date == today).scalar() or 0
        today_cap = db.query(func.sum(HandoffSlot.capacity)).filter(HandoffSlot.point_id == p.id, HandoffSlot.date == today).scalar() or 0
    # 距离估算：按用户所在宿舍区（district）粗略估算
    distance = None
    if user is not None:
        distance = 0.3 if (user.college and p.district and user.college in p.district) else 1.2
    return {
        "id": p.id,
        "name": p.name,
        "location": p.location,
        "district": p.district,
        "college": p.college,
        "open_time": p.open_time,
        "close_time": p.close_time,
        "capacity": p.capacity,
        "status": p.status,
        "today_total": int(today_cap or p.capacity),
        "today_used": int(today_used),
        "today_remain": int((today_cap or p.capacity) - today_used),
        "distance_km": distance,
        "mine": bool(p.created_by and user is not None and p.created_by == user.id),
    }


@router.get("/points", summary="交接点列表（平台预设 + 我自定义的，含今日剩余容量、距离、开放时段）")
def list_points(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(HandoffPoint).filter(HandoffPoint.status == "active")
    # 自定义点仅本人可见；平台预设点所有人可见
    q = q.filter(or_(HandoffPoint.created_by.is_(None), HandoffPoint.created_by == user.id))
    # 学院可见范围：平台管理员看全部；其他人仅看通用点（college 为空）或本学院点
    if user.role != "admin":
        q = q.filter(or_(HandoffPoint.college == "", HandoffPoint.college == (user.college or "")))
    rows = q.order_by(HandoffPoint.created_by.is_(None).desc(), HandoffPoint.id.asc()).all()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    agg = (
        db.query(HandoffSlot.point_id, func.sum(HandoffSlot.used), func.sum(HandoffSlot.capacity))
        .filter(HandoffSlot.date == today, HandoffSlot.point_id.in_([p.id for p in rows]))
        .group_by(HandoffSlot.point_id)
        .all()
    ) if rows else []
    agg_map = {pid: (used or 0, cap or 0) for pid, used, cap in agg}
    return ok([
        _point_out(db, p, user, *(agg_map.get(p.id, (0, 0)))) for p in rows
    ])


# ---------------- 用户自定义交接点（仅本人可见） ----------------
MAX_CUSTOM_POINTS = 5


def _check_hhmm(value: str, label: str) -> None:
    try:
        hh, mm = value.split(":")
        if len(hh) != 2 or len(mm) != 2:
            raise ValueError
        if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            raise ValueError
    except Exception:
        raise BizError(f"{label}格式应为 HH:MM")


@router.get("/points/mine", summary="我自定义的交接点")
def my_points(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(HandoffPoint)
        .filter(HandoffPoint.created_by == user.id, HandoffPoint.status == "active")
        .order_by(HandoffPoint.id.desc())
        .all()
    )
    return ok([_point_out(db, p, user) for p in rows])


@router.post("/points/mine", summary="用户自定义交接点（仅本人可见，发布/预约时可选用）")
def create_my_point(body: MyPointIn, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    name = (body.name or "").strip()
    location = (body.location or "").strip()
    if not name:
        raise BizError("请填写交接点名称")
    if len(name) > 40:
        raise BizError("名称不超过 40 个字")
    if len(location) > 120:
        raise BizError("位置描述不超过 120 个字")
    _check_hhmm(body.open_time, "开放时间")
    _check_hhmm(body.close_time, "关闭时间")
    if body.open_time >= body.close_time:
        raise BizError("关闭时间需晚于开放时间")

    mine = db.query(HandoffPoint).filter(
        HandoffPoint.created_by == user.id, HandoffPoint.status == "active"
    )
    if mine.count() >= MAX_CUSTOM_POINTS:
        raise BizError(f"最多只能创建 {MAX_CUSTOM_POINTS} 个自定义交接点")
    if mine.filter(HandoffPoint.name == name).first():
        raise BizError("已存在同名交接点")

    p = HandoffPoint(
        name=name,
        location=location,
        district=(body.district or "").strip(),
        open_time=body.open_time,
        close_time=body.close_time,
        capacity=params.get_param(db, "slot_capacity", 20),
        status="active",
        created_by=user.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    write_log(db, user.id, "point_create_self", f"point:{p.id}", after=p.name, request=request)
    return ok(_point_out(db, p, user), "自定义交接点已创建")


@router.delete("/points/mine/{point_id}", summary="删除我的自定义交接点")
def delete_my_point(point_id: int, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    p = db.get(HandoffPoint, point_id)
    if not p or p.created_by != user.id:
        raise BizError("交接点不存在或无权限", 404)
    busy = (
        db.query(Listing).filter(
            Listing.point_id == point_id, Listing.status.in_(["on_sale", "reserved"])
        ).count()
        + db.query(Order).filter(
            Order.point_id == point_id, Order.status.in_(["pending", "confirmed", "pending_handoff"])
        ).count()
    )
    if busy:
        raise BizError(f"该交接点还有 {busy} 个在架挂牌或进行中订单，请先处理后再删除")
    p.status = "inactive"
    db.commit()
    write_log(db, user.id, "point_delete_self", f"point:{point_id}", before=p.name, request=request)
    return ok(True, "已删除")


@router.post("/cert", summary="交接点管理员认证（平台管理员按工号认证并绑定交接点）")
def certify_point_admin(body: PointAdminCertIn, request: Request, db: Session = Depends(get_db),
                        user: User = Depends(get_admin)):
    student_no = (body.student_no or "").strip()
    if not student_no:
        raise BizError("请填写工号/学号")
    # 学号 AES 加密存储，需解密比对
    target = None
    for u in db.query(User).filter(User.status == "active").all():
        try:
            if decrypt_field(u.student_no) == student_no:
                target = u
                break
        except Exception:
            continue
    if not target:
        raise BizError("未找到该工号对应的账号", 404)

    point_id = body.point_id or target.point_id
    if point_id:
        p = db.get(HandoffPoint, point_id)
        if not p:
            raise BizError("交接点不存在", 404)
        if body.college and p.college and p.college != body.college:
            raise BizError("所选交接点与填写学院不符")
        p.manager_id = target.id
    elif body.college:
        # 未指定交接点时，若该学院已有通用交接点则绑定，否则新建一个
        p = db.query(HandoffPoint).filter(
            HandoffPoint.college == body.college, HandoffPoint.status == "active"
        ).first()
        if not p:
            p = HandoffPoint(
                name=f"{body.college}交接点", college=body.college, status="active",
                capacity=params.get_param(db, "slot_capacity", 20),
            )
            db.add(p)
            db.flush()
        p.manager_id = target.id
        point_id = p.id

    before_role = target.role
    target.role = "point_admin"
    if point_id:
        target.point_id = point_id
    db.commit()
    write_log(db, user.id, "point_admin_cert", f"user:{target.id}",
              before=before_role, after=f"point_admin/point:{point_id}", request=request)
    notify.notify(db, target.id, "交接点管理员认证", "你已被认证为交接点管理员，可在「交接点」页进行扫码核销",
                  type="system")
    return ok({"user_id": target.id, "role": "point_admin", "point_id": point_id}, "认证成功")


@router.post("/points", summary="维护交接点（管理员）")
def create_point(body: PointIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    p = HandoffPoint(**body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    write_log(db, user.id, "point_create", f"point:{p.id}", after=p.name, request=request)
    return ok(_point_out(db, p))


@router.put("/points/{point_id}")
def update_point(point_id: int, body: PointIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    p = db.get(HandoffPoint, point_id)
    if not p:
        raise BizError("交接点不存在", 404)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    write_log(db, user.id, "point_update", f"point:{point_id}", request=request)
    return ok(_point_out(db, p))


@router.delete("/points/{point_id}")
def delete_point(point_id: int, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    p = db.get(HandoffPoint, point_id)
    if not p:
        raise BizError("交接点不存在", 404)
    p.status = "inactive"
    db.commit()
    return ok(True)


@router.get("/points/{point_id}/slots", summary="查询某日可选时段（30 分钟一段）")
def slots(point_id: int, date: str = "", db: Session = Depends(get_db)):
    p = db.get(HandoffPoint, point_id)
    if not p:
        raise BizError("交接点不存在", 404)
    date = date or datetime.utcnow().strftime("%Y-%m-%d")
    cap = params.get_param(db, "slot_capacity", 20)

    def _t(h: int, m: int) -> str:
        return f"{h:02d}:{m:02d}"

    def _minutes(t: str) -> int:
        hh, mm = t.split(":")
        return int(hh) * 60 + int(mm)

    start_m, end_m = _minutes(p.open_time or "08:00"), _minutes(p.close_time or "20:00")
    exists = {s.start_time: s for s in db.query(HandoffSlot).filter(HandoffSlot.point_id == point_id, HandoffSlot.date == date).all()}
    items = []
    m = start_m
    while m < end_m:
        s_t, e_t = _t(m // 60, m % 60), _t((m + 30) // 60, (m + 30) % 60)
        s = exists.get(s_t)
        used = s.used if s else 0
        items.append({"start_time": s_t, "end_time": e_t, "capacity": cap, "used": used, "remain": cap - used,
                      "available": used < cap, "slot_id": s.id if s else None})
        m += 30
    return ok({"point": {"id": p.id, "name": p.name}, "date": date, "items": items})


@router.post("/verify", summary="交接点管理员扫码/核销码核销")
def verify_by_code(code: str, point_id: int | None = None, request: Request = None,
                   db: Session = Depends(get_db), user: User = Depends(get_point_admin)):
    o = db.query(Order).filter(Order.verify_code == code, Order.status.in_(["confirmed", "pending_handoff"])).first()
    if not o:
        raise BizError("核销码无效或订单状态不正确")
    if point_id and o.point_id and point_id != o.point_id:
        raise BizError("该订单不属于此交接点")
    o.status = "completed"
    o.completed_at = datetime.utcnow()
    l = db.get(Listing, o.listing_id)
    if l:
        l.status = "sold"
    book = db.get(Book, l.book_id) if l else None
    if book:
        book.has_deal = True
    from ..services import credit
    add = params.get_param(db, "credit_deal_add", 2)
    credit.change_credit(db, o.buyer_id, add, "deal", "order", o.id)
    credit.change_credit(db, o.seller_id, add, "deal", "order", o.id)
    db.add(OrderEvent(order_id=o.id, event="verify", remark="交接点管理员核销", operator_id=user.id))
    if o.point_id and book:
        days = params.get_param(db, "storage_days", 7)
        db.add(StorageItem(order_id=o.id, point_id=o.point_id, book_id=book.id, owner_id=o.buyer_id,
                            status="stored", due_at=datetime.utcnow() + timedelta(days=days)))
    notify.notify(db, o.buyer_id, "交接完成", f"订单 {o.order_no} 已在交接点完成核销", type="order", ref_id=o.id)
    db.commit()
    write_log(db, user.id, "handoff_verify", f"order:{o.id}", request=request)
    return ok({"order_id": o.id, "order_no": o.order_no}, "核销成功")


@router.post("/abnormal", summary="异常登记（未带证件／教材不符）")
def abnormal(order_id: int, reason: str, request: Request = None, db: Session = Depends(get_db), user: User = Depends(get_point_admin)):
    o = db.get(Order, order_id)
    if not o:
        raise BizError("订单不存在", 404)
    db.add(OrderEvent(order_id=order_id, event="abnormal", remark=reason, operator_id=user.id))
    notify.notify(db, o.buyer_id, "交接异常", f"订单 {o.order_no} 交接异常：{reason}", type="order", ref_id=order_id)
    notify.notify(db, o.seller_id, "交接异常", f"订单 {o.order_no} 交接异常：{reason}", type="order", ref_id=order_id)
    db.commit()
    write_log(db, user.id, "handoff_abnormal", f"order:{order_id}", after=reason, request=request)
    return ok(True, "已登记异常")


@router.get("/storage", summary="暂存教材列表")
def storage(point_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(StorageItem)
    if point_id:
        q = q.filter(StorageItem.point_id == point_id)
    if user.role == "point_admin":
        q = q.filter(StorageItem.point_id == user.point_id)
    elif user.role != "admin":
        q = q.filter(StorageItem.owner_id == user.id)
    rows = q.order_by(StorageItem.id.desc()).limit(100).all()
    books = load_map(db, Book, (s.book_id for s in rows))
    points = load_map(db, HandoffPoint, (s.point_id for s in rows))
    out = []
    for s in rows:
        b = books.get(s.book_id)
        p = points.get(s.point_id)
        out.append({
            "id": s.id, "book_title": b.title if b else "", "point_name": p.name if p else "",
            "status": s.status, "owner_id": s.owner_id,
            "created_at": s.created_at.isoformat(), "due_at": s.due_at.isoformat() if s.due_at else None,
            "overdue": bool(s.due_at and s.due_at < datetime.utcnow() and s.status == "stored"),
        })
    return ok(out)


@router.post("/storage/scan", summary="暂存超期处理：7 日未取转捐赠回收池")
def storage_scan(db: Session = Depends(get_db), user: User = Depends(get_admin)):
    cnt = maintenance.scan_storage(db)
    return ok({"donated": cnt}, f"已将 {cnt} 件超期暂存教材转入捐赠回收池")
