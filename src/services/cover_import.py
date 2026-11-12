from sqlalchemy.orm import Session

from ..models import Book
from .book_discovery import cover_assets
from .book_numbers import next_book_number


def import_cover_catalog(db: Session, renumber: bool = False) -> dict:
    assets = cover_assets()
    books = db.query(Book).order_by(Book.id).all()
    renumbered = 0
    if renumber:
        for book in books:
            book.isbn = "T" + str(book.id).zfill(12)
        db.flush()
        for number, book in enumerate(books, start=1):
            book.isbn = str(number).zfill(13)
            renumbered += 1
        db.flush()

    created = matched = 0
    for asset in assets:
        titles = {asset["title"], *asset.get("aliases", [])}
        matches = [book for book in books if book.cover == asset["cover"] or book.title in titles]
        if matches:
            for book in matches:
                if not book.cover or book.cover.startswith("/static/covers/"):
                    book.cover = asset["cover"]
                matched += 1
        else:
            book = Book(
                isbn=next_book_number(db),
                title=asset["title"],
                edition=asset.get("edition", ""),
                cover=asset["cover"],
                audit_status="approved",
            )
            db.add(book)
            books.append(book)
            created += 1
        db.flush()
    return {"assets": len(assets), "created": created, "matched": matched, "renumbered": renumbered, "books": len(books)}
