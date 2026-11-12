"""
数据模型（ORM）：覆盖需求文档八大功能模块。
命名规范：表名复数小写，时间字段统一 UTC 存储。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def now() -> datetime:
    return datetime.utcnow()


# ============ 1. 用户与认证 ============
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_no: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # AES 加密存储
    name: Mapped[str] = mapped_column(String(64))
    nickname: Mapped[str] = mapped_column(String(64), default="")
    phone: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # AES 加密存储
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    college: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(20), default="student", index=True)  # student/point_admin/admin
    credit_score: Mapped[int] = mapped_column(Integer, default=80)
    avatar: Mapped[str] = mapped_column(String(255), default="")
    point_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 交接点管理员所属交接点
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/disabled
    login_fail_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class WechatBinding(Base):
    """微信绑定：一个微信 openid 绑定一个账号，绑定后支持扫码免密登录"""
    __tablename__ = "wechat_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)
    openid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    unionid: Mapped[str] = mapped_column(String(128), default="", index=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    avatar: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ============ 2. 教材目录管理 ============
class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    isbn: Mapped[str] = mapped_column(String(13), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    author: Mapped[str] = mapped_column(String(255), default="")
    publisher: Mapped[str] = mapped_column(String(255), default="")
    edition: Mapped[str] = mapped_column(String(64), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)  # 原价/定价
    cover: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/stopped（停版）
    audit_status: Mapped[str] = mapped_column(String(20), default="approved")  # pending/approved/rejected
    has_deal: Mapped[bool] = mapped_column(Boolean, default=False)  # 有成交记录不可删除
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    teacher: Mapped[str] = mapped_column(String(64), default="")
    college: Mapped[str] = mapped_column(String(64), default="", index=True)
    term: Mapped[str] = mapped_column(String(32), default="")


class CourseBook(Base):
    """课程—教材 多对多关联，标记主教材/参考书/习题集"""
    __tablename__ = "course_books"
    __table_args__ = (UniqueConstraint("course_id", "book_id", name="uq_course_book"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    usage_type: Mapped[str] = mapped_column(String(20), default="主教材")


# ============ 3. 二手书发布管理 ============
class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (Index("idx_listing_book_status", "book_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    condition_level: Mapped[str] = mapped_column(String(20), index=True)
    has_notes: Mapped[bool] = mapped_column(Boolean, default=False)
    missing_pages: Mapped[bool] = mapped_column(Boolean, default=False)
    note_desc: Mapped[str] = mapped_column(Text, default="")
    images: Mapped[str] = mapped_column(Text, default="[]")  # JSON 数组字符串
    price: Mapped[float] = mapped_column(Float, index=True)
    negotiable: Mapped[bool] = mapped_column(Boolean, default=True)
    point_id: Mapped[int | None] = mapped_column(ForeignKey("handoff_points.id"), nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="on_sale", index=True)
    # on_sale / reserved / sold / off_shelf / expired / banned
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    refresh_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Wanted(Base):
    """求购单"""
    __tablename__ = "wanted"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    min_condition: Mapped[str] = mapped_column(String(20), default="有破损")
    max_price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open/closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ============ 4. 搜索与智能匹配 ============
class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "book_id", name="uq_user_book"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Message(Base):
    """站内信 + 匹配推送"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(32), default="system")  # match/order/system/credit
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ============ 5. 订单与交易流程 ============
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    point_id: Mapped[int | None] = mapped_column(ForeignKey("handoff_points.id"), nullable=True)
    slot_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending(待确认) / confirmed(已确认) / pending_handoff(待交接) / completed(已完成)
    # canceled(已取消) / appealed(已申诉) / closed(已关闭)
    verify_code: Mapped[str] = mapped_column(String(6), default="")
    appoint_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reschedule_count: Mapped[int] = mapped_column(Integer, default=0)
    cancel_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancel_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class OrderEvent(Base):
    """订单流转轨迹：履约可追溯"""
    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    event: Mapped[str] = mapped_column(String(64))
    remark: Mapped[str] = mapped_column(Text, default="")
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Appeal(Base):
    """交易申诉"""
    __tablename__ = "appeals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason_type: Mapped[str] = mapped_column(String(32))  # 货不对板/缺页/未到场/其他
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/win/lose
    result: Mapped[str] = mapped_column(Text, default="")
    credit_adjust: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ============ 6. 线下交接点管理 ============
class HandoffPoint(Base):
    __tablename__ = "handoff_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    location: Mapped[str] = mapped_column(String(255), default="")   # 位置描述
    district: Mapped[str] = mapped_column(String(64), default="")    # 宿舍区/校区，用于距离估算
    college: Mapped[str] = mapped_column(String(64), default="")     # 归属学院；空 = 全校通用
    open_time: Mapped[str] = mapped_column(String(20), default="08:00")
    close_time: Mapped[str] = mapped_column(String(20), default="20:00")
    manager_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 用户自定义交接点的创建人；NULL 表示平台预设
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class HandoffSlot(Base):
    """交接时段：每 30 分钟一段，单时段容量上限由参数配置"""
    __tablename__ = "handoff_slots"
    __table_args__ = (UniqueConstraint("point_id", "date", "start_time", name="uq_point_date_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    point_id: Mapped[int] = mapped_column(ForeignKey("handoff_points.id"), index=True)
    date: Mapped[str] = mapped_column(String(10))       # YYYY-MM-DD
    start_time: Mapped[str] = mapped_column(String(5))  # HH:MM
    end_time: Mapped[str] = mapped_column(String(5))
    capacity: Mapped[int] = mapped_column(Integer, default=20)
    used: Mapped[int] = mapped_column(Integer, default=0)


class StorageItem(Base):
    """交接点暂存教材：7 日超期转捐赠回收池"""
    __tablename__ = "storage_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    point_id: Mapped[int] = mapped_column(ForeignKey("handoff_points.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="stored")  # stored/taken/donated
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已发「临近超期」提醒


# ============ 7. 评价与信用体系 ============
class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    target_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rating_desc: Mapped[int] = mapped_column(Integer, default=5)       # 描述相符
    rating_condition: Mapped[int] = mapped_column(Integer, default=5)   # 成色真实
    rating_punctual: Mapped[int] = mapped_column(Integer, default=5)   # 履约及时
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class CreditLog(Base):
    __tablename__ = "credit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    score_after: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(String(255), default="")
    ref_type: Mapped[str] = mapped_column(String(32), default="")
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ============ 8. 后台管理与统计 ============
class Report(Base):
    """违规下架 / 举报处理"""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_type: Mapped[str] = mapped_column(String(20))  # listing/user
    target_id: Mapped[int] = mapped_column(Integer)
    reason_type: Mapped[str] = mapped_column(String(32))  # 盗版/非教材/图片违规/虚假描述/骚扰
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    handle_result: Mapped[str] = mapped_column(Text, default="")
    handler_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Donation(Base):
    """捐赠回收：学生捐赠 → 平台回收 → 赠予困难学生（学工部审核）"""
    __tablename__ = "donations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/approved/recycled/donated
    beneficiary: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SysParam(Base):
    """可配置业务参数，禁止硬编码"""
    __tablename__ = "sys_params"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    param_key: Mapped[str] = mapped_column(String(64), unique=True)
    param_value: Mapped[str] = mapped_column(String(255))
    remark: Mapped[str] = mapped_column(String(255), default="")


class OperationLog(Base):
    """操作日志留痕：操作人、时间、IP、变更前后值，保留 180 天"""
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(128), default="")
    before: Mapped[str] = mapped_column(Text, default="")
    after: Mapped[str] = mapped_column(Text, default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
