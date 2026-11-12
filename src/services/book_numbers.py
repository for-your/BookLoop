from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.response import BizError
from ..models import Book


def normalize_book_number(value: str) -> str:
    number = str(value or "").strip()
    if not number:
        return ""
    if not number.isascii() or not number.isdigit() or len(number) > 13:
        raise BizError("书籍编号须为 1 至 13 位数字，系统会补齐为 13 位")
    return number.zfill(13)


def reserve_book_numbers(rows: list[tuple], columns: list[int]) -> set[str]:
    reserved = set()
    for row in rows:
        for column in columns:
            if column >= len(row) or row[column] is None or not str(row[column]).strip():
                continue
            try:
                reserved.add(normalize_book_number(str(row[column])))
            except BizError:
                pass
            break
    return reserved


def next_book_number(db: Session, reserved: set[str] | None = None) -> str:
    numbers = [int(number) for number, in db.query(Book.isbn).all() if number.isascii() and number.isdigit()]
    candidate = max(numbers, default=0) + 1
    while str(candidate).zfill(13) in (reserved or set()):
        candidate += 1
    if candidate > 9999999999999:
        raise BizError("书籍编号已达到 13 位上限")
    return str(candidate).zfill(13)


def check_book_number(db: Session, value: str, current_id: int | None = None) -> str:
    number = normalize_book_number(value) or next_book_number(db)
    duplicate = db.query(Book).filter(Book.isbn == number)
    if current_id is not None:
        duplicate = duplicate.filter(Book.id != current_id)
    if duplicate.first():
        raise BizError("书籍编号已存在，请使用其他编号或留空自动生成")
    return number


def commit_book(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as failure:
        db.rollback()
        raise BizError("书籍编号已存在，请刷新后重试") from failure
