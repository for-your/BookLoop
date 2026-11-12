"""
模块五：订单与交易流程模块
状态机：待确认(pending) → 已确认(confirmed) → 待交接(pending_handoff) → 已完成(completed)
分支：已取消(canceled) / 已申诉(appealed) / 已关闭(closed)
业务规则：预约锁定 24h、卖方 24h 未确认自动释放、改约最多 2 次、违约扣分、
交接核销码 6 位、超时 48h 自动关闭双方各扣 3 分。
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..core.response import BizError, ok
from ..core.security import decrypt_field, mask_phone
from ..db import get_db
from ..models import (
    Appeal,
    Book,
    HandoffPoint,
    HandoffSlot,
    Listing,
    Order,
    OrderEvent,
    StorageItem,
    User,
)
from ..schemas import AppealIn, CancelIn, OrderCreateIn, RescheduleIn, VerifyIn
from ..services import credit, maintenance, notify, params
from ..services.batch import load_map
from ..services.log import write_log

router = APIRouter(prefix="/orders", tags=["订单与交易流程"])

STATUS_TEXT = {
    "pending": "待确认",
    "confirmed": "已确认",
    "pending_handoff": "待交接",
    "completed": "已完成",
    "canceled": "已取消",
    "appealed": "已申诉",
    "closed": "已关闭",
}


def _gen_code() -> str:
    return "".join(random.choices("0123456789", k=6))


def _serialize_orders(db: Session, orders: list[Order], viewer: User | None = None) -> list[dict]:
    """批量序列化订单：一次加载挂牌/教材/买卖双方/交接点，避免 N+1。"""
    listings = load_map(db, Listing, (o.listing_id for o in orders))
    books = load_map(db, Book, (l.book_id for l in listings.values()))
    users = load_map(db, User, [o.buyer_id for o in orders] + [o.seller_id for o in orders])
    points = load_map(db, HandoffPoint, (o.point_id for o in orders))

    out = []
    for o in orders:
        l = listings.get(o.listing_id)
        book = books.get(l.book_id) if l else None
        buyer = users.get(o.buyer_id)
        seller = users.get(o.seller_id)
        point = points.get(o.point_id)

        # 联系方式脱敏：确认前掩码，确认后展示（防跳单）
        show_full = o.status in ("confirmed", "pending_handoff", "completed")
        buyer_phone = decrypt_field(buyer.phone) if buyer else ""
        seller_phone = decrypt_field(seller.phone) if seller else ""
        if not show_full:
            buyer_phone = mask_phone(buyer_phone)
            seller_phone = mask_phone(seller_phone)

        out.append({
            "id": o.id,
            "order_no": o.order_no,
            "listing_id": o.listing_id,
            "book_title": book.title if book else "",
            "cover": book.cover if book else "",
            "condition_level": l.condition_level if l else "",
            "price": o.price,
            "status": o.status,
            "status_text": STATUS_TEXT.get(o.status, o.status),
            "buyer_id": o.buyer_id,
            "seller_id": o.seller_id,
            "buyer_name": (buyer.nickname or buyer.name) if buyer else "",
            "seller_name": (seller.nickname or seller.name) if seller else "",
            "buyer_phone": buyer_phone,
            "seller_phone": seller_phone,
            "point_name": point.name if point else "",
            "point_location": point.location if point else "",
            "appoint_at": o.appoint_at.isoformat() if o.appoint_at else None,
            "verify_code": o.verify_code if o.status in ("confirmed", "pending_handoff") else "",
            "reschedule_count": o.reschedule_count,
            "created_at": o.created_at.isoformat(),
            "role": ("buyer" if viewer and viewer.id == o.buyer_id else "seller" if viewer else ""),
        })
    return out


def _order_out(db: Session, o: Order, viewer: User | None = None) -> dict:
    return _serialize_orders(db, [o], viewer)[0]


def _get_slot(db: Session, point_id: int, appoint_at: datetime) -> HandoffSlot:
    """按 30 分钟粒度获取/创建交接时段，并校验容量"""
    cap = params.get_param(db, "slot_capacity", 20)
    date_s = appoint_at.strftime("%Y-%m-%d")
    minute = 0 if appoint_at.minute < 30 else 30
    start = f"{appoint_at.hour:02d}:{minute:02d}"
    end_dt = (appoint_at.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=30 if minute == 0 else 60))
    end = f"{end_dt.hour:02d}:{end_dt.minute:02d}"
    slot = (
        db.query(HandoffSlot)
        .filter(HandoffSlot.point_id == point_id, HandoffSlot.date == date_s, HandoffSlot.start_time == start)
        .first()
    )
    if not slot:
        slot = HandoffSlot(point_id=point_id, date=date_s, start_time=start, end_time=end, capacity=cap, used=0)
        db.add(slot)
        db.flush()
    return slot


@router.post("", summary="预约下单（锁定教材 24 小时）")
def create_order(body: OrderCreateIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = db.get(Listing, body.listing_id)
    if not l:
        raise BizError("挂牌不存在", 404)
    if l.status != "on_sale":
        raise BizError("该教材已被预约或下架")
    if l.seller_id == user.id:
        raise BizError("不能预约自己发布的教材")
    # 信用分只限制发布；信用受限的学生仍可预约购买。
    # 锁定 24 小时
    lock_h = params.get_param(db, "reserve_lock_hours", 24)
    l.status = "reserved"

    appoint_at = body.appoint_at or (datetime.utcnow() + timedelta(days=1))
    point_id = l.point_id
    slot = None
    if point_id:
        slot = _get_slot(db, point_id, appoint_at)
        if slot.used >= slot.capacity:
            l.status = "on_sale"
            db.commit()
            raise BizError("该交接时段已约满，请选择其他时段")
        slot.used += 1

    order = Order(
        order_no=f"BC{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}",
        listing_id=l.id,
        buyer_id=user.id,
        seller_id=l.seller_id,
        point_id=point_id,
        slot_id=slot.id if slot else None,
        price=l.price,
        status="pending",
        verify_code=_gen_code(),
        appoint_at=appoint_at,
    )
    db.add(order)
    db.flush()
    db.add(OrderEvent(order_id=order.id, event="create", remark=f"预约下单，锁定 {lock_h} 小时", operator_id=user.id))
    notify.notify(db, l.seller_id, "收到新预约", f"你发布的教材被预约，请在 24 小时内确认（订单号 {order.order_no}）",
                  type="order", ref_id=order.id)
    db.commit()
    write_log(db, user.id, "order_create", f"order:{order.id}", after=order.order_no, request=request)
    return ok(_order_out(db, order, user), "预约成功，等待卖方确认")


@router.get("", summary="我的订单")
def my_orders(status: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Order).filter((Order.buyer_id == user.id) | (Order.seller_id == user.id))
    if status:
        q = q.filter(Order.status == status)
    rows = q.order_by(Order.id.desc()).limit(100).all()
    return ok(_serialize_orders(db, rows, user))


# 静态路径须置于 /{order_id} 之前，避免被动态路由抢占
@router.get("/appeals/mine")
def my_appeals(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Appeal).filter(Appeal.applicant_id == user.id).order_by(Appeal.id.desc()).all()
    return ok([
        {"id": r.id, "order_id": r.order_id, "reason_type": r.reason_type, "detail": r.detail,
         "status": r.status, "result": r.result, "credit_adjust": r.credit_adjust,
         "created_at": r.created_at.isoformat()}
        for r in rows
    ])


@router.get("/{order_id}")
def order_detail(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = db.get(Order, order_id)
    if not o:
        raise BizError("订单不存在", 404)
    if user.id not in (o.buyer_id, o.seller_id) and user.role != "admin":
        raise BizError("无权查看该订单", 403)
    data = _order_out(db, o, user)
    events = db.query(OrderEvent).filter(OrderEvent.order_id == o.id).order_by(OrderEvent.id).all()
    data["events"] = [
        {"event": e.event, "remark": e.remark, "created_at": e.created_at.isoformat()} for e in events
    ]
    # 倒计时
    if o.status == "pending":
        deadline = o.created_at + timedelta(hours=params.get_param(db, "confirm_timeout_hours", 24))
        data["confirm_deadline"] = deadline.isoformat()
    return ok(data)


@router.post("/{order_id}/confirm", summary="卖方确认预约")
def confirm(order_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = db.get(Order, order_id)
    if not o or o.seller_id != user.id:
        raise BizError("订单不存在或无权操作", 404)
    if o.status != "pending":
        raise BizError("当前状态不可确认")
    o.status = "confirmed"
    o.confirmed_at = datetime.utcnow()
    db.add(OrderEvent(order_id=o.id, event="confirm", remark="卖方确认预约", operator_id=user.id))
    notify.notify(db, o.buyer_id, "卖方已确认", f"订单 {o.order_no} 已确认，请按时到交接点完成交接", type="order", ref_id=o.id)
    db.commit()
    write_log(db, user.id, "order_confirm", f"order:{order_id}", request=request)
    return ok(_order_out(db, o, user), "已确认，联系方式已对双方开放")


@router.post("/{order_id}/reschedule", summary="协商改约（最多 2 次）")
def reschedule(order_id: int, body: RescheduleIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = db.get(Order, order_id)
    if not o or user.id not in (o.buyer_id, o.seller_id):
        raise BizError("订单不存在或无权操作", 404)
    if o.status not in ("pending", "confirmed", "pending_handoff"):
        raise BizError("当前状态不可改约")
    max_r = params.get_param(db, "max_reschedule", 2)
    if o.reschedule_count >= max_r:
        raise BizError(f"改约次数已达上限（{max_r} 次）")
    # 释放原时段
    if o.slot_id:
        old = db.get(HandoffSlot, o.slot_id)
        if old and old.used > 0:
            old.used -= 1
    slot = _get_slot(db, o.point_id, body.appoint_at) if o.point_id else None
    if slot and slot.used >= slot.capacity:
        raise BizError("该时段已约满")
    if slot:
        slot.used += 1
        o.slot_id = slot.id
    o.appoint_at = body.appoint_at
    o.reschedule_count += 1
    db.add(OrderEvent(order_id=o.id, event="reschedule", remark=f"改约至 {body.appoint_at}", operator_id=user.id))
    peer = o.seller_id if user.id == o.buyer_id else o.buyer_id
    notify.notify(db, peer, "对方申请改约", f"订单 {o.order_no} 改约至 {body.appoint_at.strftime('%m-%d %H:%M')}",
                  type="order", ref_id=o.id)
    db.commit()
    return ok(_order_out(db, o, user), "改约成功")


@router.post("/{order_id}/cancel", summary="取消订单（违约扣分）")
def cancel(order_id: int, body: CancelIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = db.get(Order, order_id)
    if not o or user.id not in (o.buyer_id, o.seller_id):
        raise BizError("订单不存在或无权操作", 404)
    if o.status in ("completed", "canceled", "closed"):
        raise BizError("该订单无法取消")

    # 临近交接 2 小时内取消扣 10 分，否则扣 5 分
    urgent_h = params.get_param(db, "cancel_urgent_hours", 2)
    urgent = o.appoint_at and (o.appoint_at - datetime.utcnow()) <= timedelta(hours=urgent_h)
    penalty = params.get_param(db, "cancel_penalty_urgent" if urgent else "cancel_penalty", 5)
    credit.change_credit(db, user.id, -penalty, "break_urgent" if urgent else "break", "order", o.id)

    if o.slot_id:
        slot = db.get(HandoffSlot, o.slot_id)
        if slot and slot.used > 0:
            slot.used -= 1
    l = db.get(Listing, o.listing_id)
    if l and l.status == "reserved":
        l.status = "on_sale"

    o.status = "canceled"
    o.cancel_by = user.id
    o.cancel_reason = body.reason
    db.add(OrderEvent(order_id=o.id, event="cancel", remark=f"取消，扣分 {penalty}", operator_id=user.id))
    peer = o.seller_id if user.id == o.buyer_id else o.buyer_id
    notify.notify(db, peer, "订单被取消", f"订单 {o.order_no} 已被对方取消", type="order", ref_id=o.id)
    db.commit()
    write_log(db, user.id, "order_cancel", f"order:{order_id}", after=body.reason, request=request)
    return ok(_order_out(db, o, user), f"已取消，违约扣 {penalty} 分")


@router.post("/{order_id}/verify", summary="交接核销（扫码 / 6 位核销码）")
def verify(order_id: int, body: VerifyIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = db.get(Order, order_id)
    if not o:
        raise BizError("订单不存在", 404)
    is_point_admin = user.role in ("point_admin", "admin")
    if not (user.id in (o.buyer_id, o.seller_id) or is_point_admin):
        raise BizError("无权核销", 403)
    if o.status not in ("confirmed", "pending_handoff"):
        raise BizError("订单未确认，无法核销")
    if body.code != o.verify_code:
        raise BizError("核销码错误")
    if is_point_admin and body.point_id and o.point_id and body.point_id != o.point_id:
        raise BizError("交接点与订单不匹配")

    o.status = "completed"
    o.completed_at = datetime.utcnow()
    l = db.get(Listing, o.listing_id)
    if l:
        l.status = "sold"
    book = db.get(Book, l.book_id) if l else None
    if book:
        book.has_deal = True

    add = params.get_param(db, "credit_deal_add", 2)
    credit.change_credit(db, o.buyer_id, add, "deal", "order", o.id)
    credit.change_credit(db, o.seller_id, add, "deal", "order", o.id)

    db.add(OrderEvent(order_id=o.id, event="verify", remark="交接核销完成", operator_id=user.id))
    # 暂存记录：交付后进入交接点暂存（7 日）
    if o.point_id and book:
        days = params.get_param(db, "storage_days", 7)
        db.add(
            StorageItem(
                order_id=o.id,
                point_id=o.point_id,
                book_id=book.id,
                owner_id=o.buyer_id,
                status="stored",
                due_at=datetime.utcnow() + timedelta(days=days),
            )
        )
    notify.notify(db, o.buyer_id, "交易完成", f"订单 {o.order_no} 已完成，请于 7 日内互评", type="order", ref_id=o.id)
    notify.notify(db, o.seller_id, "交易完成", f"订单 {o.order_no} 已完成，信用分 +{add}", type="order", ref_id=o.id)
    db.commit()
    write_log(db, user.id, "order_verify", f"order:{order_id}", request=request)
    return ok(_order_out(db, o, user), "核销成功，交易完成")


@router.post("/{order_id}/appeal", summary="交易申诉（交付后 7 日内）")
def appeal(order_id: int, body: AppealIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = db.get(Order, order_id)
    if not o or user.id not in (o.buyer_id, o.seller_id):
        raise BizError("订单不存在或无权操作", 404)
    if o.status != "completed":
        raise BizError("仅已完成的订单可申诉")
    if o.completed_at and (datetime.utcnow() - o.completed_at) > timedelta(days=7):
        raise BizError("超过 7 日申诉期")
    a = Appeal(order_id=o.id, applicant_id=user.id, reason_type=body.reason_type, detail=body.detail, status="pending")
    db.add(a)
    o.status = "appealed"
    db.add(OrderEvent(order_id=o.id, event="appeal", remark=f"申诉：{body.reason_type}", operator_id=user.id))
    db.commit()
    return ok({"id": a.id}, "申诉已提交，管理员将在 3 个工作日内裁定")


@router.post("/scan-timeout", summary="超时扫描：确认超时释放 + 交接超时关闭")
def scan_timeout(db: Session = Depends(get_db)):
    """由定时任务（或管理员）调用：24h 未确认释放；超过约定时段 48h 未核销自动关闭"""
    return ok(maintenance.scan_orders(db), "超时扫描完成")
