"""
智能匹配服务：求购 ↔ 在架货源 双向匹配、收藏到货提醒。
匹配条件：同一 ISBN + 成色不低于求购下限 + 价格不高于心理价位上限。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.config import CONDITION_LEVELS
from ..models import Book, Favorite, Listing, Wanted
from . import notify


def condition_rank(level: str) -> int:
    """成色越新 rank 越小：全新=0 ... 有破损=5"""
    try:
        return CONDITION_LEVELS.index(level)
    except ValueError:
        return len(CONDITION_LEVELS)


def _satisfy(listing: Listing, wanted: Wanted) -> bool:
    if listing.book_id != wanted.book_id or listing.status != "on_sale":
        return False
    if wanted.max_price and listing.price > wanted.max_price:
        return False
    # 求购方可接受成色下限：货源成色需不差于下限（rank 更小或相等）
    if condition_rank(listing.condition_level) > condition_rank(wanted.min_condition):
        return False
    return True


def match_for_wanted(db: Session, wanted: Wanted, push: bool = True) -> list[Listing]:
    """为求购单找货源"""
    candidates = db.query(Listing).filter(Listing.book_id == wanted.book_id, Listing.status == "on_sale").all()
    hits = [l for l in candidates if _satisfy(l, wanted)]
    if push and hits:
        book = db.get(Book, wanted.book_id)
        for l in hits:
            notify.notify(
                db,
                wanted.user_id,
                "求购有新货源",
                f"《{book.title if book else ''}》有 {len(hits)} 本符合条件的在架教材，最低 "
                f"{min(x.price for x in hits):.2f} 元，快去看看吧！",
                type="match",
                ref_id=l.id,
            )
        db.commit()
    return hits


def match_for_listing(db: Session, listing: Listing) -> int:
    """新货源上架：反向匹配所有未关闭求购单 + 收藏到货提醒"""
    book = db.get(Book, listing.book_id)
    wanteds = db.query(Wanted).filter(Wanted.book_id == listing.book_id, Wanted.status == "open").all()
    hit_count = 0
    for w in wanteds:
        if _satisfy(listing, w):
            hit_count += 1
            notify.notify(
                db,
                w.user_id,
                "有同学发布了你要的教材",
                f"《{book.title if book else ''}》{listing.condition_level}，售价 {listing.price:.2f} 元",
                type="match",
                ref_id=listing.id,
            )
    # 收藏提醒
    favs = db.query(Favorite).filter(Favorite.book_id == listing.book_id).all()
    for f in favs:
        if f.user_id == listing.seller_id:
            continue
        notify.notify(
            db,
            f.user_id,
            "收藏的教材到货",
            f"你收藏的《{book.title if book else ''}》有新货源上架：{listing.condition_level} / {listing.price:.2f} 元",
            type="match",
            ref_id=listing.id,
        )
    db.commit()
    return hit_count


def condition_options() -> list[str]:
    return list(CONDITION_LEVELS)
