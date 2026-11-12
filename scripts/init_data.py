"""从 data/seed/demo.json 增量初始化演示数据；--reset 会清空当前配置的数据库。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import SEED_DIR
from src.core.security import encrypt_field, hash_password
from src.db import SessionLocal, init_db
from src.models import Book, Course, CourseBook, HandoffPoint, Listing, User, Wanted, WechatBinding
from src.services.book_numbers import next_book_number
from src.services.cover_import import import_cover_catalog
from src.services.wechat import DEMO_OPENID


def seed_points(db, rows):
    points = {}
    for row in rows:
        point = db.query(HandoffPoint).filter(HandoffPoint.name == row["name"]).first()
        if point is None:
            point = HandoffPoint(**row, capacity=20)
            db.add(point)
            db.flush()
        points[row["name"]] = point
    return points


def seed_users(db, rows, points):
    users = {}
    for row in rows:
        student_no = row["student_no"]
        encrypted_no = encrypt_field(student_no)
        user = db.query(User).filter(User.student_no == encrypted_no).first()
        if user is None:
            password = os.getenv("ADMIN_PWD", "admin@2026") if row["role"] == "admin" else os.getenv("DEMO_PWD", "campus@2026")
            user = User(
                student_no=encrypted_no,
                name=row["name"],
                nickname=row["name"],
                phone=encrypt_field("138" + student_no[-8:].rjust(8, "0")),
                password_hash=hash_password(password),
                college=row["college"],
                role=row["role"],
                credit_score=row["credit_score"],
            )
            db.add(user)
            db.flush()
        # 只补齐演示管理员的空归属，不覆盖后台已经指定的交接点。
        if row.get("point") and user.point_id is None:
            user.point_id = points[row["point"]].id
        users[student_no] = user

    if not db.query(WechatBinding).filter(WechatBinding.openid == DEMO_OPENID).first():
        db.add(WechatBinding(user_id=users["20230001"].id, openid=DEMO_OPENID, nickname="微信演示用户"))
    return users


def seed_books(db, rows):
    books = {}
    for row in rows:
        book = db.query(Book).filter(Book.title == row["title"], Book.edition == row["edition"]).first()
        if book is None:
            values = {key: value for key, value in row.items() if key != "usage"}
            book = Book(**values, isbn=next_book_number(db), cover="", audit_status="approved")
            db.add(book)
            db.flush()
        books[row["title"]] = book
    return books


def seed_courses(db, rows, book_rows, books):
    for row in rows:
        course = db.query(Course).filter(Course.code == row["code"]).first()
        if course is None:
            values = {key: value for key, value in row.items() if key != "book_keyword"}
            course = Course(**values)
            db.add(course)
            db.flush()
        keyword = row["book_keyword"]
        for book_row in book_rows:
            book = books[book_row["title"]]
            if book.title.startswith(keyword) or keyword.startswith(book.title[:4]):
                link = db.query(CourseBook).filter(CourseBook.course_id == course.id, CourseBook.book_id == book.id).first()
                if link is None:
                    db.add(CourseBook(course_id=course.id, book_id=book.id, usage_type=book_row["usage"]))
                    db.flush()


def seed_listings(db, rows, users, books, points):
    for row in rows:
        seller = users[row["seller"]]
        book = books[row["book"]]
        if db.query(Listing).filter(Listing.seller_id == seller.id, Listing.book_id == book.id).first():
            continue
        db.add(Listing(
            book_id=book.id,
            seller_id=seller.id,
            condition_level=row["condition_level"],
            has_notes=row["has_notes"],
            price=row["price"],
            negotiable=row["negotiable"],
            point_id=points[row["point"]].id,
            images="[]",
            status="on_sale",
            remark="课程结束后闲置，欢迎自取",
            expire_at=datetime.utcnow() + timedelta(days=90),
        ))


def seed_wanted(db, rows, users, books):
    for row in rows:
        user = users[row["student"]]
        book = books[row["book"]]
        if not db.query(Wanted).filter(Wanted.user_id == user.id, Wanted.book_id == book.id).first():
            db.add(Wanted(user_id=user.id, book_id=book.id, min_condition=row["min_condition"], max_price=row["max_price"], status="open"))


def seed(reset: bool = False) -> None:
    with (SEED_DIR / "demo.json").open(encoding="utf-8") as source:
        data = json.load(source)
    init_db(drop=reset)
    # 按外键依赖顺序写入；统一提交，失败时会话关闭并回滚业务数据。
    with SessionLocal() as db:
        points = seed_points(db, data["points"])
        users = seed_users(db, data["users"], points)
        books = seed_books(db, data["books"])
        seed_courses(db, data["courses"], data["books"], books)
        seed_listings(db, data["listings"], users, books, points)
        seed_wanted(db, data["wanted"], users, books)
        import_cover_catalog(db)
        db.commit()
        print(
            f"演示数据初始化完成：用户 {db.query(User).count()} / 教材 {db.query(Book).count()} / "
            f"课程 {db.query(Course).count()} / 挂牌 {db.query(Listing).count()} / 交接点 {db.query(HandoffPoint).count()}"
        )
        print("演示账号和默认密码见 README.md；自定义密码使用 DEMO_PWD / ADMIN_PWD。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="删除当前数据库全部表并重新初始化演示数据")
    seed(reset=parser.parse_args().reset)
