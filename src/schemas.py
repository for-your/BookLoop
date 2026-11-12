"""接口出入参模型（Pydantic v2）"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssistantMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)
    book_ids: list[int] = Field(default_factory=list, max_length=3)


class AssistantIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    message: str = Field(min_length=1, max_length=1000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=8)
    book_id: int | None = Field(default=None, gt=0)
    model: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def check_history(self):
        if sum(len(message.content) for message in self.history) > 6000:
            raise ValueError("对话历史过长，请开启新对话")
        return self


class RegisterIn(BaseModel):
    student_no: str = Field(..., min_length=6, max_length=20, description="学号")
    name: str
    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=6, max_length=64)
    college: str = ""
    role: str = "student"  # student / point_admin


class LoginIn(BaseModel):
    student_no: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    code: Optional[str] = None  # 手机验证码（演示环境：任意 6 位即可，生产对接学校短信网关）


class WechatRegisterIn(BaseModel):
    """微信首次登录未绑定账号时，绑定学号创建账号"""
    wechat_token: str
    student_no: str = Field(..., min_length=6, max_length=20)
    name: str
    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=6, max_length=64)
    college: str = ""


class BookIn(BaseModel):
    isbn: str = Field("", max_length=13, description="平台书籍编号，留空自动分配；1 至 13 位数字补齐为 13 位")
    title: str
    author: str = ""
    publisher: str = ""
    edition: str = ""
    price: float = 0
    cover: str = ""


class CourseIn(BaseModel):
    code: str
    name: str
    teacher: str = ""
    college: str = ""
    term: str = ""


class CourseBookIn(BaseModel):
    course_id: int
    book_id: int
    usage_type: str = "主教材"


class ListingIn(BaseModel):
    book_id: Optional[int] = None
    isbn: Optional[str] = None
    condition_level: str
    has_notes: bool = False
    missing_pages: bool = False
    note_desc: str = ""
    images: list[str] = []
    price: float
    negotiable: bool = True
    point_id: Optional[int] = None
    remark: str = ""


class WantedIn(BaseModel):
    book_id: int
    min_condition: str = "有破损"
    max_price: float = 0


class OrderCreateIn(BaseModel):
    listing_id: int
    slot_id: Optional[int] = None
    appoint_at: Optional[datetime] = None


class RescheduleIn(BaseModel):
    slot_id: Optional[int] = None
    appoint_at: datetime


class CancelIn(BaseModel):
    reason: str = ""


class VerifyIn(BaseModel):
    code: str
    point_id: Optional[int] = None


class AppealIn(BaseModel):
    reason_type: str
    detail: str = ""


class ReviewIn(BaseModel):
    order_id: int
    rating_desc: int = Field(5, ge=1, le=5)
    rating_condition: int = Field(5, ge=1, le=5)
    rating_punctual: int = Field(5, ge=1, le=5)
    comment: str = ""


class PointIn(BaseModel):
    name: str
    location: str = ""
    district: str = ""
    college: str = ""
    open_time: str = "08:00"
    close_time: str = "20:00"
    manager_id: Optional[int] = None
    capacity: int = 20


class MyPointIn(BaseModel):
    """用户自定义交接点：不允许设置容量/负责人，容量取自系统参数"""
    name: str
    location: str = ""
    district: str = ""
    open_time: str = "08:00"
    close_time: str = "20:00"


class PointAdminCertIn(BaseModel):
    """交接点管理员认证（平台管理员操作）"""
    student_no: str
    college: str = ""
    point_id: Optional[int] = None


class ReportIn(BaseModel):
    target_type: str
    target_id: int
    reason_type: str
    detail: str = ""


class DonationIn(BaseModel):
    book_id: Optional[int] = None
    isbn: Optional[str] = None
    title: str = ""
    quantity: int = 1


class ParamIn(BaseModel):
    key: str
    value: str
    remark: str = ""


class ReviewAppealIn(BaseModel):
    """申诉复核：管理员裁定"""
    status: str  # win / lose
    result: str = ""
    credit_adjust: int = 0
