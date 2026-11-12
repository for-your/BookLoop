from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from ..core.response import BizError
from ..models import Book, Course, CourseBook
from .book_numbers import next_book_number, normalize_book_number, reserve_book_numbers


def import_catalog(db: Session, source: str | BytesIO) -> dict:
    """读取教材 Excel，更新目录及课程关联；事务由调用方提交。"""
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        rows = list(workbook.active.iter_rows(values_only=True))
    finally:
        workbook.close()

    result = {"created_book": 0, "updated": 0, "created_course": 0, "linked": 0, "skipped": 0, "errors": []}
    if not rows:
        result["errors"].append("空文件")
        return result

    columns = {str(value).strip(): index for index, value in enumerate(rows[0]) if value is not None}
    reserved = reserve_book_numbers(rows[1:], [columns[name] for name in ("书籍编号", "ISBN") if name in columns])

    for row_number, row in enumerate(rows[1:], start=2):
        if all(value is None for value in row):
            continue

        def cell(name: str, default=""):
            column = columns.get(name)
            if column is None or column >= len(row) or row[column] is None:
                return default
            return str(row[column]).strip()

        title = cell("书名")
        if not title:
            result["skipped"] += 1
            result["errors"].append(f"第{row_number}行：书名缺失")
            continue
        try:
            number = normalize_book_number(cell("书籍编号") or cell("ISBN"))
        except BizError:
            result["skipped"] += 1
            result["errors"].append(f"第{row_number}行：书籍编号须为 1 至 13 位数字")
            continue

        book = (db.query(Book).filter(Book.isbn == number).first() if number
                else db.query(Book).filter(Book.title == title, Book.edition == cell("版次")).first())
        if book:
            book.title = title
            book.author = cell("作者", book.author)
            book.publisher = cell("出版社", book.publisher)
            book.edition = cell("版次", book.edition)
            try:
                book.price = float(cell("定价", str(book.price)) or book.price)
            except ValueError:
                pass
            result["updated"] += 1
        else:
            book = Book(
                isbn=number or next_book_number(db, reserved), title=title,
                author=cell("作者"), publisher=cell("出版社"), edition=cell("版次"),
                price=float(cell("定价", "0") or 0), cover="", audit_status="approved",
            )
            db.add(book)
            result["created_book"] += 1
        db.flush()

        code = cell("课程代码")
        if code:
            course = db.query(Course).filter(Course.code == code).first()
            if not course:
                course = Course(code=code, name=cell("课程名"), teacher=cell("任课教师"), college=cell("学院"), term=cell("学期"))
                db.add(course)
                db.flush()
                result["created_course"] += 1
            if not db.query(CourseBook).filter(CourseBook.course_id == course.id, CourseBook.book_id == book.id).first():
                db.add(CourseBook(course_id=course.id, book_id=book.id, usage_type=cell("用途", "主教材")))
                db.flush()
                result["linked"] += 1

    result["errors"] = result["errors"][:50]
    return result
