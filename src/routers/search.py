"""
模块四：搜索与智能匹配模块
关键词检索（书名/作者/ISBN/课程名/课程代码）、条件筛选、课程一键找书、
双向匹配、收藏与到货提醒。检索响应目标 < 1s（5 万条挂牌）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Book, Course, CourseBook, Favorite, HandoffPoint, Listing, User
from ..core.deps import get_current_user
from ..core.response import BizError, ok
from ..services import matching
from ..services.batch import load_map
from ..services.book_discovery import book_visuals, category_expression, listing_images

router = APIRouter(prefix="/search", tags=["搜索与智能匹配"])


def _query_set(db: Session, keyword="", college="", condition="", min_price=None, max_price=None,
               point_id=None, negotiable=None, course_id=None, category="", course_college=""):
    q = db.query(Listing).filter(Listing.status == "on_sale")
    if course_id:
        q = q.filter(Listing.book_id.in_(select(CourseBook.book_id).where(CourseBook.course_id == course_id)))
    if course_college:
        linked_books = select(CourseBook.book_id).join(Course, Course.id == CourseBook.course_id).where(Course.college == course_college)
        q = q.filter(Listing.book_id.in_(linked_books))
    if category:
        q = q.filter(Listing.book_id.in_(select(Book.id).where(category_expression() == category)))
    if keyword:
        like = f"%{keyword}%"
        book_sub = select(Book.id).where(
            or_(Book.title.like(like), Book.author.like(like), Book.isbn.like(like)))
        course_sub = select(Course.id).where(
            or_(Course.name.like(like), Course.code.like(like)))
        cb_sub = select(CourseBook.book_id).where(CourseBook.course_id.in_(course_sub))
        q = q.filter(or_(Listing.book_id.in_(book_sub), Listing.book_id.in_(cb_sub)))
    if condition:
        q = q.filter(Listing.condition_level == condition)
    if min_price is not None:
        q = q.filter(Listing.price >= min_price)
    if max_price is not None:
        q = q.filter(Listing.price <= max_price)
    if point_id:
        q = q.filter(Listing.point_id == point_id)
    if negotiable is not None:
        q = q.filter(Listing.negotiable.is_(negotiable))
    if college:
        q = q.filter(Listing.seller_id.in_(select(User.id).where(User.college == college)))
    return q


def _serialize(db: Session, listings: list[Listing]) -> list[dict]:
    """批量序列化挂牌列表：一次查询关联的教材/卖家/交接点，避免 N+1。"""
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
            "price": l.price,
            "negotiable": l.negotiable,
            "point_id": l.point_id,
            "point_name": point.name if point else "",
            "status": l.status,
            "images": images,
            "remark": l.remark,
            "view_count": l.view_count,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        })
    return out


def _out(db: Session, l: Listing) -> dict:
    return _serialize(db, [l])[0]


@router.get("", summary="关键词检索 + 条件筛选")
def search(
    keyword: str = "",
    college: str = "",
    condition: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    point_id: int | None = None,
    negotiable: bool | None = None,
    course_id: int | None = None,
    category: str = "",
    course_college: str = "",
    sort: str = "time_desc",
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
):
    q = _query_set(db, keyword, college, condition, min_price, max_price, point_id, negotiable, course_id, category, course_college)
    total = q.count()
    if sort == "price_asc":
        q = q.order_by(Listing.price.asc())
    elif sort == "price_desc":
        q = q.order_by(Listing.price.desc())
    elif sort == "view_desc":
        q = q.order_by(Listing.view_count.desc())
    else:
        q = q.order_by(Listing.created_at.desc())
    rows = q.offset((page - 1) * size).limit(size).all()
    return ok({"total": total, "page": page, "size": size, "items": _serialize(db, rows)})


@router.get("/course/{course_id}", summary="课程一键找书")
def by_course(course_id: int, sort: str = "price_asc", db: Session = Depends(get_db)):
    q = _query_set(db, course_id=course_id)
    if sort == "time_desc":
        q = q.order_by(Listing.created_at.desc())
    else:
        q = q.order_by(Listing.price.asc())
    rows = q.limit(100).all()
    course = db.get(Course, course_id)
    return ok({"course": {"id": course.id, "name": course.name, "code": course.code} if course else None,
               "items": _serialize(db, rows)})


# ---------------- 收藏 ----------------
@router.post("/favorites/{book_id}", summary="收藏教材（到货提醒）")
def add_fav(book_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.book_id == book_id).first():
        db.add(Favorite(user_id=user.id, book_id=book_id))
        db.commit()
    return ok(True, "已收藏，有货源将提醒你")


@router.delete("/favorites/{book_id}")
def del_fav(book_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Favorite).filter(Favorite.user_id == user.id, Favorite.book_id == book_id).delete()
    db.commit()
    return ok(True)


@router.get("/favorites/mine")
def my_favs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Favorite).filter(Favorite.user_id == user.id).all()
    books = load_map(db, Book, (f.book_id for f in rows))
    # 一次分组查询统计各收藏教材的在架数量
    cnt_rows = (
        db.query(Listing.book_id, func.count(Listing.id))
        .filter(Listing.book_id.in_(books.keys()), Listing.status == "on_sale")
        .group_by(Listing.book_id)
        .all()
    ) if books else []
    cnt_map = {bid: n for bid, n in cnt_rows}
    items = []
    for f in rows:
        b = books.get(f.book_id)
        items.append({"book_id": f.book_id, "title": b.title if b else "", "isbn": b.isbn if b else "",
                      **book_visuals(b), "on_sale": cnt_map.get(f.book_id, 0),
                      "created_at": f.created_at.isoformat()})
    return ok(items)


@router.get("/conditions", summary="成色档位（可配置）")
def conditions():
    return ok(matching.condition_options())


# 注意：动态路径路由必须置于静态路径之后，否则会抢占 /search/conditions 等路由
@router.get("/{listing_id}", summary="挂牌详情（浏览数 +1）")
def detail(listing_id: int, db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if not l:
        raise BizError("挂牌不存在", 404)
    l.view_count += 1
    db.commit()
    data = _out(db, l)
    book = db.get(Book, l.book_id)
    if book:
        links = db.query(CourseBook).filter(CourseBook.book_id == book.id).all()
        data["courses"] = [
            {"id": c.id, "name": c.name, "code": c.code, "usage_type": lk.usage_type}
            for lk in links
            for c in [db.get(Course, lk.course_id)]
            if c
        ]
    return ok(data)
