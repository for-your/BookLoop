"""
周期性维护任务（纯函数，供后台调度线程与手动接口复用）：
- 订单超时：卖方 24h 未确认自动释放；超过约定时段 48h 未核销自动关闭并双方扣分；
- 挂牌到期：超过有效期（默认 90 天）自动下架；
- 暂存超期：交接点暂存 7 日未取自动转入捐赠回收池；
- 闲置下架：账号连续 N 个月（默认 12）未登录，自动下架其全部在架教材并提醒。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import Book, Donation, HandoffSlot, Listing, Order, OrderEvent, StorageItem, User
from . import credit, notify, params
from .batch import load_map


def scan_orders(db: Session) -> dict:
    """订单超时关闭/释放 + 挂牌到期下架。返回各维度处理数量。"""
    now = datetime.utcnow()
    confirm_h = params.get_param(db, "confirm_timeout_hours", 24)
    overtime_h = params.get_param(db, "order_overtime_hours", 48)
    penalty = params.get_param(db, "overtime_penalty", 3)

    released = closed = 0
    # 卖方 24 小时未确认：释放锁定教材与时段，关闭订单
    pendings = db.query(Order).filter(Order.status == "pending").all()
    for o in pendings:
        if (now - o.created_at) > timedelta(hours=confirm_h):
            l = db.get(Listing, o.listing_id)
            if l and l.status == "reserved":
                l.status = "on_sale"
            if o.slot_id:
                s = db.get(HandoffSlot, o.slot_id)
                if s and s.used > 0:
                    s.used -= 1
            o.status = "closed"
            db.add(OrderEvent(order_id=o.id, event="auto_close", remark="卖方超时未确认，自动释放"))
            notify.notify(db, o.buyer_id, "订单已关闭", f"订单 {o.order_no} 卖方超时未确认，已自动关闭",
                          type="order", ref_id=o.id)
            released += 1

    # 超过约定时段 48 小时未核销：双方各扣分并关闭
    actives = db.query(Order).filter(Order.status.in_(["confirmed", "pending_handoff"])).all()
    for o in actives:
        base = o.appoint_at or o.confirmed_at or o.created_at
        if (now - base) > timedelta(hours=overtime_h):
            credit.change_credit(db, o.buyer_id, -penalty, "overtime", "order", o.id)
            credit.change_credit(db, o.seller_id, -penalty, "overtime", "order", o.id)
            if o.slot_id:
                s = db.get(HandoffSlot, o.slot_id)
                if s and s.used > 0:
                    s.used -= 1
            l = db.get(Listing, o.listing_id)
            if l and l.status == "reserved":
                l.status = "on_sale"
            o.status = "closed"
            db.add(OrderEvent(order_id=o.id, event="auto_close", remark=f"超时未核销，双方各扣 {penalty} 分"))
            notify.notify(db, o.buyer_id, "订单超时关闭", f"订单 {o.order_no} 超时未核销，信用分 -{penalty}",
                          type="order", ref_id=o.id)
            notify.notify(db, o.seller_id, "订单超时关闭", f"订单 {o.order_no} 超时未核销，信用分 -{penalty}",
                          type="order", ref_id=o.id)
            closed += 1

    # 挂牌到期自动下架
    expired = 0
    on_sale = db.query(Listing).filter(Listing.status == "on_sale").all()
    books = load_map(db, Book, (l.book_id for l in on_sale))
    for l in on_sale:
        if l.expire_at and l.expire_at < now:
            l.status = "expired"
            b = books.get(l.book_id)
            notify.notify(db, l.seller_id, "挂牌到期",
                          f"你的挂牌《{b.title if b else ''}》已到期自动下架", type="system")
            expired += 1
    db.commit()
    return {"released": released, "closed": closed, "expired_listings": expired}


def scan_storage(db: Session) -> int:
    """暂存超期（7 日未取）自动转入捐赠回收池；到期前 24h 内提前提醒一次。返回转入数量。"""
    now = datetime.utcnow()

    # 临近超期：到期前 24 小时内、未提醒过的，提前发一次提醒
    soon = (
        db.query(StorageItem)
        .filter(
            StorageItem.status == "stored",
            StorageItem.reminded.is_(False),
            StorageItem.due_at.isnot(None),
            StorageItem.due_at >= now,
            StorageItem.due_at < now + timedelta(hours=24),
        )
        .all()
    )
    for s in soon:
        notify.notify(
            db, s.owner_id, "暂存即将到期",
            f"你暂存的教材将于 {s.due_at.strftime('%m-%d %H:%M')} 到期，请尽快取件，逾期将转入捐赠回收池",
            type="system", ref_id=s.id,
        )
        s.reminded = True

    rows = db.query(StorageItem).filter(StorageItem.status == "stored", StorageItem.due_at < now).all()
    cnt = 0
    for s in rows:
        s.status = "donated"
        db.add(Donation(user_id=s.owner_id, book_id=s.book_id, quantity=1, status="recycled"))
        notify.notify(db, s.owner_id, "暂存超期", "你暂存的教材超过 7 日未取，已转入捐赠回收池", type="system")
        cnt += 1
    db.commit()
    return cnt


def scan_idle_users(db: Session) -> int:
    """连续 N 个月未登录的用户，自动下架其全部在架教材并提醒。返回下架数量。"""
    months = params.get_param(db, "idle_months_offline", 12)
    cutoff = datetime.utcnow() - timedelta(days=months * 30)
    idle_ids = [
        u[0] for u in db.query(User.id)
        .filter(User.last_login_at.isnot(None), User.last_login_at < cutoff)
        .all()
    ]
    if not idle_ids:
        return 0
    rows = db.query(Listing).filter(
        Listing.seller_id.in_(idle_ids), Listing.status == "on_sale"
    ).all()
    affected = {l.seller_id for l in rows}
    for l in rows:
        l.status = "off_shelf"
    for uid in affected:
        notify.notify(db, uid, "账号长期未登录，挂牌已下架",
                      f"你的账号连续 {months} 个月未登录，系统已自动下架全部在架教材，重新登录后可再次上架",
                      type="system")
    db.commit()
    return len(rows)


def run_all(db: Session) -> dict:
    """依次执行全部维护任务，返回汇总结果。"""
    return {
        "orders": scan_orders(db),
        "storage": scan_storage(db),
        "idle": scan_idle_users(db),
    }
