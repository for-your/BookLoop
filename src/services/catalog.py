from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Book, Course, CourseBook, Listing
from .batch import load_map
from .book_discovery import book_visuals


def serialize_books(db: Session, books: list[Book]) -> list[dict]:
    book_ids = [book.id for book in books]
    links = db.query(CourseBook).filter(CourseBook.book_id.in_(book_ids)).all() if book_ids else []
    courses = load_map(db, Course, (link.course_id for link in links))
    link_by_book: dict[int, list] = {}
    for link in links:
        link_by_book.setdefault(link.book_id, []).append(link)
    stats_map = {}
    if book_ids:
        stats_rows = (
            db.query(Listing.book_id, func.count(Listing.id), func.min(Listing.price))
            .filter(Listing.book_id.in_(book_ids), Listing.status == "on_sale")
            .group_by(Listing.book_id)
            .all()
        )
        stats_map = {book_id: (count, price) for book_id, count, price in stats_rows}
    result = []
    for book in books:
        course_list = []
        for link in link_by_book.get(book.id, []):
            course = courses.get(link.course_id)
            if course:
                course_list.append({
                    "id": course.id, "code": course.code, "name": course.name,
                    "teacher": course.teacher, "college": course.college, "usage_type": link.usage_type,
                })
        count, price = stats_map.get(book.id, (0, None))
        result.append({
            "id": book.id, "isbn": book.isbn, "title": book.title, "author": book.author,
            "publisher": book.publisher, "edition": book.edition, "price": book.price,
            **book_visuals(book), "status": book.status, "audit_status": book.audit_status,
            "courses": course_list, "on_sale_count": count or 0, "min_price": price,
        })
    return result
