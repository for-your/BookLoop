"""
模块三：二手书发布管理模块
- 发布出售（价格上限 70%、成色 6 档、图片必填、有效期 90 天）
- 发布求购、挂牌管理（上/下架、编辑、刷新）、违规处理
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import CONDITION_LEVELS
from ..core.deps import get_admin, get_current_user
from ..core.response import BizError, ok
from ..db import get_db
from ..models import Book, HandoffPoint, Listing, Order, User, Wanted
from ..schemas import ListingIn, WantedIn
from ..services import credit, matching, notify, params
from ..services.batch import load_map
from ..services.book_discovery import book_visuals, listing_images
from ..services.log import write_log

router = APIRouter(prefix="/listings", tags=["二手书发布管理"])


def _check_publishable(db: Session, user: User) -> None:
    if not credit.can_publish(db, user):
        raise BizError(f"信用分低于 {params.get_param(db, 'credit_publish_min', 60)} 分，禁止发布新教材，仅可购买")


def _serialize_listings(db: Session, listings: list[Listing]) -> list[dict]:
    """批量序列化挂牌：一次加载教材/卖家/交接点，避免 N+1。"""
    books = load_map(db, Book, (l.book_id for l in listings))
    sellers = load_map(db, User, (l.seller_id for l in listings))
    points = load_map(db, HandoffPoint, (l.point_id for l in listings))

    out = []
    for l in listings:
        book = books.get(l.book_id)
        seller = sellers.get(l.seller_id)
        point = points.get(l.point_id)
        images = listing_images(l.images)
        out.append({
            "id": l.id,
            "book_id": l.book_id,
            "book_title": book.title if book else "",
            "isbn": book.isbn if book else "",
            **book_visuals(book),
            "original_price": book.price if book else 0,
            "seller_id": l.seller_id,
            "seller_name": (seller.nickname or seller.name) if seller else "",
            "seller_college": seller.college if seller else "",
            "condition_level": l.condition_level,
            "has_notes": l.has_notes,
            "missing_pages": l.missing_pages,
            "price": l.price,
            "negotiable": l.negotiable,
            "point_id": l.point_id,
            "point_name": point.name if point else "",
            "status": l.status,
            "images": images,
            "remark": l.remark,
            "view_count": l.view_count,
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "expire_at": l.expire_at.isoformat() if l.expire_at else None,
        })
    return out


def _listing_out(db: Session, l: Listing) -> dict:
    return _serialize_listings(db, [l])[0]


@router.get("/price-suggest", summary="系统建议售价区间（原价 30%-70%）")
def price_suggest(book_id: int = None, isbn: str = None, db: Session = Depends(get_db)):
    book = db.get(Book, book_id) if book_id else db.query(Book).filter(Book.isbn == isbn).first()
    if not book:
        raise BizError("教材不存在", 404)
    ratio_max = float(params.get_param(db, "price_ratio_max", 0.7))
    ratio_min = float(params.get_param(db, "price_ratio_min_suggest", 0.3))
    return ok(
        {
            "original_price": book.price,
            "min": round(book.price * ratio_min, 2),
            "max": round(book.price * ratio_max, 2),
            "max_ratio": ratio_max,
        }
    )


@router.post("", summary="发布出售")
def create_listing(body: ListingIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_publishable(db, user)

    book = db.get(Book, body.book_id) if body.book_id else None
    if not book and body.isbn:
        book = db.query(Book).filter(Book.isbn == body.isbn).first()
    if not book:
        raise BizError("请先选择教材（支持书籍编号检索）", 404)
    if book.audit_status != "approved":
        raise BizError("该教材目录尚未审核通过")

    if body.condition_level not in CONDITION_LEVELS:
        raise BizError(f"成色必须为 6 档之一：{'/'.join(CONDITION_LEVELS)}")
    if not body.images:
        raise BizError("请至少上传 1 张实物照片")
    if not body.point_id:
        raise BizError("请选择交接点")

    ratio_max = float(params.get_param(db, "price_ratio_max", 0.7))
    if book.price > 0 and body.price > round(book.price * ratio_max, 2):
        raise BizError(f"售价不得高于原价的 {int(ratio_max * 100)}%（上限 {round(book.price * ratio_max, 2)} 元）")

    max_on = params.get_param(db, "max_on_sale_per_user", 20)
    cur = (
        db.query(func.count(Listing.id))
        .filter(Listing.seller_id == user.id, Listing.status == "on_sale")
        .scalar()
        or 0
    )
    if cur >= max_on:
        raise BizError(f"单用户在架教材上限 {max_on} 本，请先下架部分教材")

    max_same = params.get_param(db, "max_same_isbn_per_user", 3)
    same = (
        db.query(func.count(Listing.id))
        .filter(Listing.seller_id == user.id, Listing.book_id == book.id, Listing.status == "on_sale")
        .scalar()
        or 0
    )
    if same >= max_same:
        raise BizError(f"同一用户对同一书籍在架不得超过 {max_same} 本")

    valid_days = params.get_param(db, "listing_valid_days", 90)
    import json

    listing = Listing(
        book_id=book.id,
        seller_id=user.id,
        condition_level=body.condition_level,
        has_notes=body.has_notes,
        missing_pages=body.missing_pages,
        note_desc=body.note_desc,
        images=json.dumps(body.images, ensure_ascii=False),
        price=body.price,
        negotiable=body.negotiable,
        point_id=body.point_id,
        remark=body.remark,
        status="on_sale",
        expire_at=datetime.utcnow() + timedelta(days=valid_days),
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)

    # 发布即做一次双向匹配，命中推送站内信
    hit = matching.match_for_listing(db, listing)
    write_log(db, user.id, "listing_create", f"listing:{listing.id}", after=f"{book.isbn}/{body.price}", request=request)
    db.commit()
    return ok({**_listing_out(db, listing), "matched_wanted": hit}, "发布成功，已为你匹配求购需求" if hit else "发布成功")


@router.get("/mine", summary="挂牌管理：我的发布")
def my_listings(status: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Listing).filter(Listing.seller_id == user.id)
    if status:
        q = q.filter(Listing.status == status)
    rows = q.order_by(Listing.id.desc()).limit(100).all()
    return ok(_serialize_listings(db, rows))


@router.put("/{listing_id}", summary="编辑挂牌")
def update_listing(
    listing_id: int,
    body: ListingIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    l = db.get(Listing, listing_id)
    if not l or l.seller_id != user.id:
        raise BizError("挂牌不存在或无权操作", 404)
    if l.status not in ("on_sale", "off_shelf"):
        raise BizError("当前状态不可编辑")
    book = db.get(Book, l.book_id)
    ratio_max = float(params.get_param(db, "price_ratio_max", 0.7))
    if book and book.price > 0 and body.price > round(book.price * ratio_max, 2):
        raise BizError(f"售价不得高于原价的 {int(ratio_max * 100)}%")

    l.condition_level = body.condition_level
    l.has_notes = body.has_notes
    l.missing_pages = body.missing_pages
    l.note_desc = body.note_desc
    l.price = body.price
    l.negotiable = body.negotiable
    l.point_id = body.point_id or l.point_id
    l.remark = body.remark
    if body.images:
        import json
        l.images = json.dumps(body.images, ensure_ascii=False)
    db.commit()
    write_log(db, user.id, "listing_update", f"listing:{listing_id}", after=str(body.price), request=request)
    return ok(_listing_out(db, l), "已更新")


@router.post("/{listing_id}/off-shelf")
def off_shelf(listing_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = db.get(Listing, listing_id)
    if not l or l.seller_id != user.id:
        raise BizError("挂牌不存在或无权操作", 404)
    l.status = "off_shelf"
    db.commit()
    write_log(db, user.id, "listing_off", f"listing:{listing_id}", request=request)
    return ok(True, "已下架")


@router.post("/{listing_id}/on-shelf")
def on_shelf(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = db.get(Listing, listing_id)
    if not l or l.seller_id != user.id:
        raise BizError("挂牌不存在或无权操作", 404)
    _check_publishable(db, user)
    max_on = params.get_param(db, "max_on_sale_per_user", 20)
    cur = db.query(func.count(Listing.id)).filter(Listing.seller_id == user.id, Listing.status == "on_sale").scalar() or 0
    if cur >= max_on:
        raise BizError(f"单用户在架上限 {max_on} 本")
    valid_days = params.get_param(db, "listing_valid_days", 90)
    l.status = "on_sale"
    l.refresh_at = datetime.utcnow()
    l.expire_at = datetime.utcnow() + timedelta(days=valid_days)
    db.commit()
    matching.match_for_listing(db, l)
    return ok(True, "已上架")


@router.post("/{listing_id}/refresh", summary="刷新挂牌（重置有效期）")
def refresh_listing(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = db.get(Listing, listing_id)
    if not l or l.seller_id != user.id:
        raise BizError("挂牌不存在或无权操作", 404)
    valid_days = params.get_param(db, "listing_valid_days", 90)
    l.refresh_at = datetime.utcnow()
    l.expire_at = datetime.utcnow() + timedelta(days=valid_days)
    db.commit()
    return ok(True, "已刷新，有效期延长 90 天")


@router.delete("/{listing_id}", summary="删除挂牌")
def delete_listing(listing_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    l = db.get(Listing, listing_id)
    if not l or l.seller_id != user.id:
        raise BizError("挂牌不存在或无权操作", 404)
    # 已有交易记录时不可删除，保护订单流水与双方历史，可改为下架
    if db.query(Order.id).filter(Order.listing_id == l.id).first():
        raise BizError("该挂牌已有交易记录，无法删除，可改为下架")
    db.delete(l)
    db.commit()
    write_log(db, user.id, "listing_delete", f"listing:{listing_id}", request=request)
    return ok(True, "已删除")


@router.post("/{listing_id}/ban", summary="违规下架（管理员）")
def ban_listing(
    listing_id: int,
    reason_type: str = "虚假描述",
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_admin),
):
    l = db.get(Listing, listing_id)
    if not l:
        raise BizError("挂牌不存在", 404)
    from ..models import Report

    l.status = "banned"
    db.add(
        Report(
            reporter_id=user.id,
            target_type="listing",
            target_id=listing_id,
            reason_type=reason_type,
            status="handled",
            handle_result="管理员下架",
            handler_id=user.id,
        )
    )
    notify.notify(db, l.seller_id, "挂牌被下架", f"你的挂牌因「{reason_type}」被管理员下架", type="system")
    db.commit()
    write_log(db, user.id, "listing_ban", f"listing:{listing_id}", after=reason_type, request=request)
    return ok(True, "已下架并记录违规")


# ---------------- 求购 ----------------
@router.post("/wanted", summary="发布求购")
def create_wanted(body: WantedIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    book = db.get(Book, body.book_id)
    if not book:
        raise BizError("教材不存在", 404)
    if body.min_condition not in CONDITION_LEVELS:
        raise BizError(f"成色下限必须为 6 档之一：{'/'.join(CONDITION_LEVELS)}")
    w = Wanted(
        user_id=user.id,
        book_id=body.book_id,
        min_condition=body.min_condition,
        max_price=body.max_price,
        status="open",
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    hits = matching.match_for_wanted(db, w)
    return ok({"id": w.id, "matched": len(hits)}, f"求购已发布，命中 {len(hits)} 个货源" if hits else "求购已发布，有货将通知你")


@router.get("/wanted/mine")
def my_wanted(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Wanted).filter(Wanted.user_id == user.id).order_by(Wanted.id.desc()).all()
    books = load_map(db, Book, (w.book_id for w in rows))
    out = []
    for w in rows:
        b = books.get(w.book_id)
        hits = matching.match_for_wanted(db, w, push=False)
        out.append(
            {
                "id": w.id,
                "book_id": w.book_id,
                "book_title": b.title if b else "",
                "min_condition": w.min_condition,
                "max_price": w.max_price,
                "status": w.status,
                "matched": len(hits),
                "created_at": w.created_at.isoformat(),
            }
        )
    return ok(out)


@router.delete("/wanted/{wanted_id}")
def close_wanted(wanted_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    w = db.get(Wanted, wanted_id)
    if not w or w.user_id != user.id:
        raise BizError("求购单不存在", 404)
    w.status = "closed"
    db.commit()
    return ok(True)
