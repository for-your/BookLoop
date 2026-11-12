"""
模块二：教材目录管理模块
- 教材库维护（手动/Excel 批量导入，平台书籍编号 13 位唯一）
- 课程—教材多对多关联、目录审核、目录查询
"""
from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..core.deps import get_admin, get_current_user
from ..core.response import BizError, ok
from ..db import get_db
from ..models import Book, Course, CourseBook, User
from ..schemas import BookIn, CourseBookIn, CourseIn
from ..services.batch import load_map
from ..services.book_discovery import CATEGORIES, category_expression
from ..services.book_numbers import check_book_number, commit_book
from ..services.catalog import serialize_books as _serialize_books
from ..services.catalog_import import import_catalog
from ..services.log import write_log

router = APIRouter(prefix="/catalog", tags=["教材目录管理"])


def _book_out(db: Session, b: Book) -> dict:
    return _serialize_books(db, [b])[0]


@router.get("/cover-library", summary="已导入真实封面的教材目录")
def cover_library(category: str = "", keyword: str = "", page: int = 1, size: int = 12, db: Session = Depends(get_db)):
    query = db.query(Book).filter(Book.audit_status == "approved", Book.cover != "")
    if category:
        query = query.filter(category_expression() == category)
    if keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(Book.title.like(like), Book.isbn.like(like)))
    page = max(1, page)
    size = min(max(1, size), 100)
    start = (page - 1) * size
    total = query.count()
    books = query.order_by(Book.id).offset(start).limit(size).all()
    return ok({"total": total, "page": page, "size": size, "items": _serialize_books(db, books)})


@router.get("/facets", summary="教材学科分类与开课学院")
def discovery_facets(db: Session = Depends(get_db)):
    expression = category_expression()
    counts = dict(db.query(expression, func.count(Book.id)).filter(Book.audit_status == "approved").group_by(expression).all())
    cover_counts = dict(db.query(expression, func.count(Book.id)).filter(Book.audit_status == "approved", Book.cover != "").group_by(expression).all())
    colleges = db.query(Course.college, func.count(Course.id)).filter(Course.college != "").group_by(Course.college).order_by(Course.college).all()
    return ok({
        "categories": [{"id": category, "name": name, "count": counts.get(category, 0), "cover_count": cover_counts.get(category, 0)} for category, name, keywords in CATEGORIES],
        "colleges": [{"name": college, "course_count": count} for college, count in colleges],
    })


@router.post("/books", summary="新增教材条目（平台书籍编号 13 位唯一，留空自动分配）")
def create_book(body: BookIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    values = body.model_dump()
    values["isbn"] = check_book_number(db, body.isbn)
    book = Book(**values, audit_status="pending")
    db.add(book)
    commit_book(db)
    db.refresh(book)
    write_log(db, user.id, "book_create", f"book:{book.id}", after=book.isbn, request=request)
    return ok(_book_out(db, book), "已提交，等待管理员审核")


@router.get("/books/{book_id}", summary="教材详情：封面/元数据 + 关联课程 + 在架二手书")
def book_detail(book_id: int, db: Session = Depends(get_db)):
    b = db.get(Book, book_id)
    if not b:
        raise BizError("教材不存在", 404)
    return ok(_book_out(db, b))


@router.get("/books", summary="目录查询（按课程名/课程代码/教师/学院/书名）")
def list_books(
    keyword: str = "",
    college: str = "",
    course_id: int | None = None,
    category: str = "",
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
):
    q = db.query(Book).filter(Book.audit_status == "approved")
    if keyword:
        like = f"%{keyword}%"
        matched_course_ids = [
            c.id for c in db.query(Course).filter(Course.name.like(like) | Course.code.like(like)).all()
        ]
        matched_book_ids = (
            []
            if not matched_course_ids
            else [x.book_id for x in db.query(CourseBook).filter(CourseBook.course_id.in_(matched_course_ids)).all()]
        )
        q = q.filter(
            or_(Book.title.like(like), Book.author.like(like), Book.isbn.like(like), Book.id.in_(matched_book_ids))
        )
    if course_id:
        ids = [x.book_id for x in db.query(CourseBook).filter(CourseBook.course_id == course_id).all()]
        q = q.filter(Book.id.in_(ids))
    if college:
        course_books = db.query(CourseBook.book_id).join(Course, Course.id == CourseBook.course_id).filter(Course.college == college)
        q = q.filter(Book.id.in_(course_books))
    if category:
        q = q.filter(category_expression() == category)
    total = q.count()
    rows = q.order_by(Book.id.desc()).offset((page - 1) * size).limit(size).all()
    return ok({"total": total, "items": _serialize_books(db, rows)})


@router.put("/books/{book_id}")
def update_book(book_id: int, body: BookIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    b = db.get(Book, book_id)
    if not b:
        raise BizError("教材不存在", 404)
    before = f"{b.title}/{b.price}"
    values = body.model_dump()
    values["isbn"] = check_book_number(db, body.isbn or b.isbn, current_id=b.id)
    for k, v in values.items():
        setattr(b, k, v)
    commit_book(db)
    write_log(db, user.id, "book_update", f"book:{book_id}", before=before, after=f"{b.title}/{b.price}", request=request)
    return ok(_book_out(db, b))


@router.delete("/books/{book_id}", summary="删除（有成交记录仅标记停版）")
def delete_book(book_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    b = db.get(Book, book_id)
    if not b:
        raise BizError("教材不存在", 404)
    if b.has_deal:
        b.status = "stopped"
        db.commit()
        write_log(db, user.id, "book_stop", f"book:{book_id}", after="存在成交记录，标记为停版", request=request)
        return ok({"stopped": True}, "该教材已有成交记录，已标记为停版")
    db.query(CourseBook).filter(CourseBook.book_id == book_id).delete()
    db.delete(b)
    db.commit()
    write_log(db, user.id, "book_delete", f"book:{book_id}", request=request)
    return ok({"deleted": True})


@router.post("/books/{book_id}/audit", summary="目录审核（查重、封面合规）")
def audit_book(
    book_id: int,
    approved: bool = True,
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_admin),
):
    b = db.get(Book, book_id)
    if not b:
        raise BizError("教材不存在", 404)
    b.audit_status = "approved" if approved else "rejected"
    db.commit()
    write_log(db, user.id, "book_audit", f"book:{book_id}", after=b.audit_status, request=request)
    return ok(_book_out(db, b), "审核完成")


@router.post("/books/import", summary="Excel 批量导入教材目录 + 课程关联")
async def import_books(
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_admin),
):
    """Excel 列：课程代码、课程名、书籍编号（可空，兼容 ISBN）、书名、作者、出版社、版次、定价。"""
    result = import_catalog(db, BytesIO(await file.read()))
    db.commit()
    write_log(
        db,
        user.id,
        "book_import",
        f"file:{file.filename}",
        after=f"新增教材{result['created_book']}/更新{result['updated']}/新增课程{result['created_course']}/关联{result['linked']}/跳过{result['skipped']}",
        request=request,
    )
    return ok(
        result,
        f"导入完成：新增教材 {result['created_book']} 条，关联 {result['linked']} 条",
    )


@router.get("/import/template", summary="下载批量导入模板")
def import_template():
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["课程代码", "课程名", "书籍编号", "书名", "作者", "出版社", "版次", "定价", "任课教师", "学院", "学期", "用途"])
    ws.append(["CS101", "数据结构", "", "数据结构（C语言版）", "严蔚敏", "人民邮电出版社", "第2版", "45.00", "张三", "计算机学院", "2026-2027-1", "主教材"])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=book_import_template.xlsx"},
    )


# ---------------- 课程 ----------------
@router.post("/courses")
def create_course(body: CourseIn, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    c = db.query(Course).filter(Course.code == body.code).first()
    if c:
        raise BizError("课程代码已存在")
    c = Course(**body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return ok({"id": c.id, "code": c.code, "name": c.name, "teacher": c.teacher, "college": c.college, "term": c.term})


@router.get("/courses")
def list_courses(college: str = "", keyword: str = "", db: Session = Depends(get_db)):
    q = db.query(Course)
    if college:
        q = q.filter(Course.college == college)
    if keyword:
        q = q.filter(Course.name.like(f"%{keyword}%") | Course.code.like(f"%{keyword}%"))
    rows = q.order_by(Course.id.desc()).limit(200).all()
    return ok([{"id": r.id, "code": r.code, "name": r.name, "teacher": r.teacher, "college": r.college, "term": r.term} for r in rows])


@router.post("/course-books", summary="建立课程—教材关联")
def link_course_book(body: CourseBookIn, db: Session = Depends(get_db), user: User = Depends(get_admin)):
    if db.query(CourseBook).filter(CourseBook.course_id == body.course_id, CourseBook.book_id == body.book_id).first():
        raise BizError("该关联已存在")
    lk = CourseBook(**body.model_dump())
    db.add(lk)
    db.commit()
    return ok({"id": lk.id})


@router.get("/courses/{course_id}/books", summary="按课程查教材清单")
def course_books(course_id: int, db: Session = Depends(get_db)):
    links = db.query(CourseBook).filter(CourseBook.course_id == course_id).all()
    books = load_map(db, Book, (lk.book_id for lk in links))
    s_map = {d["id"]: d for d in _serialize_books(db, list(books.values()))}
    items = []
    for lk in links:
        d = s_map.get(lk.book_id)
        if d:
            d = dict(d)
            d["usage_type"] = lk.usage_type
            items.append(d)
    return ok(items)
