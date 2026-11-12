"""
模块一：用户与认证模块
- 学号唯一注册、学号/手机验证码登录、登录失败锁定
- 三级角色 RBAC、个人中心、信用分详情、站内消息
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ROLE_STUDENT
from ..core.deps import get_current_user, touch_login
from ..core.rate_limit import client_ip, hit
from ..core.response import BizError, ok
from ..core.security import (
    create_access_token,
    create_refresh_token,
    create_wechat_token,
    decode_token,
    decrypt_field,
    encrypt_field,
    hash_password,
    mask_phone,
    mask_student_no,
    verify_password,
)
from ..db import get_db
from ..models import Book, Favorite, Listing, Message, Order, Review, User, Wanted, WechatBinding
from ..schemas import LoginIn, RegisterIn, WechatRegisterIn
from ..services import credit, notify, params, wechat
from ..services.batch import load_map
from ..services.book_discovery import book_visuals, listing_images
from ..services.log import write_log

router = APIRouter(prefix="/auth", tags=["用户与认证"])

# 演示用验证码存储（生产接入学校短信网关 + Redis）
_SMS_CODES: dict[str, str] = {}


def _user_out(db: Session, u: User) -> dict:
    on_sale = (
        db.query(func.count(Listing.id))
        .filter(Listing.seller_id == u.id, Listing.status == "on_sale")
        .scalar()
        or 0
    )
    deals = (
        db.query(func.count(Order.id))
        .filter(Order.status == "completed", Order.buyer_id == u.id)
        .scalar()
        or 0
    )
    return {
        "id": u.id,
        "student_no": mask_student_no(decrypt_field(u.student_no)),
        "name": u.name,
        "nickname": u.nickname or u.name,
        "college": u.college,
        "role": u.role,
        "credit_score": u.credit_score,
        "credit_level": credit.level_of(u.credit_score),
        "avatar": u.avatar,
        "on_sale_count": on_sale,
        "deal_count": deals,
    }


@router.post("/send-code")
def send_code(phone: str, request: Request, db: Session = Depends(get_db)):
    """发送验证码（演示环境固定 888888，生产对接学校短信网关）"""
    if not hit(f"send_code:{client_ip(request)}", 1, 60):
        raise BizError("请求过于频繁，请 60 秒后再试")
    code = "888888"
    _SMS_CODES[phone] = code
    try:
        notify.notify(db, 0, "验证码", f"手机号 {mask_phone(phone)} 的登录验证码为 {code}", type="system")
    except Exception:
        pass
    print(f"[SMS] 验证码 -> {phone}: {code}")
    return ok({"sent": True, "dev_code": code}, "验证码已发送（演示环境返回明文）")


@router.post("/register", summary="注册（学号唯一）")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    enc_no = encrypt_field(body.student_no)
    if db.query(User).filter(User.student_no == enc_no).first():
        raise BizError("该学号已注册")
    enc_phone = encrypt_field(body.phone)
    if db.query(User).filter(User.phone == enc_phone).first():
        raise BizError("该手机号已绑定其他账号")

    init_score = params.get_param(db, "credit_init", 80)
    user = User(
        student_no=enc_no,
        name=body.name,
        nickname=body.name,
        phone=enc_phone,
        password_hash=hash_password(body.password),
        college=body.college,
        role=body.role if body.role in (ROLE_STUDENT, "point_admin") else ROLE_STUDENT,
        credit_score=init_score,
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    credit.change_credit(db, user.id, 0, "register", "user", user.id)
    write_log(db, user.id, "register", f"user:{user.id}", after=body.student_no, request=request)
    db.commit()
    return ok(_user_out(db, user), "注册成功")


@router.post("/login", summary="学号密码 / 手机验证码登录")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = None
    if body.phone and body.code:
        enc_phone = encrypt_field(body.phone)
        user = db.query(User).filter(User.phone == enc_phone).first()
        if user is None:
            raise BizError("该手机号未注册")
        if _SMS_CODES.get(body.phone) != body.code and body.code != "888888":
            raise BizError("验证码错误")
    elif body.student_no and body.password:
        enc_no = encrypt_field(body.student_no)
        user = db.query(User).filter(User.student_no == enc_no).first()
        if user is None:
            raise BizError("学号或密码错误")
    else:
        raise BizError("请提供学号+密码 或 手机号+验证码")

    # 登录失败锁定：5 次锁定 15 分钟
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise BizError(f"登录失败次数过多，请 {(user.locked_until - datetime.utcnow()).seconds // 60 + 1} 分钟后重试")
    if body.password and not verify_password(body.password, user.password_hash):
        user.login_fail_count += 1
        if user.login_fail_count >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
            user.login_fail_count = 0
            db.commit()
            raise BizError("登录失败 5 次，账号已锁定 15 分钟")
        db.commit()
        raise BizError(f"学号或密码错误（剩余尝试次数 {5 - user.login_fail_count}）")
    if user.status != "active":
        raise BizError("账号已被禁用，请联系教务处")

    touch_login(user, db)
    write_log(db, user.id, "login", f"user:{user.id}", request=request)

    return ok(
        {
            "access_token": create_access_token(user.id, {"role": user.role}),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": _user_out(db, user),
        },
        "登录成功",
    )


@router.post("/refresh")
def refresh(token: str, db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise BizError("刷新令牌无效")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise BizError("用户不存在")
    return ok(
        {
            "access_token": create_access_token(user.id, {"role": user.role}),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


# ---------------- 微信扫码免密登录 ----------------

def _wechat_token(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, {"role": user.role}),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/wechat/login-url", summary="微信登录地址（公众号 OAuth / 开放平台扫码）")
def wechat_login_url(redirect_uri: str = ""):
    state = secrets.token_hex(8)
    return ok(
        {
            "url": "" if wechat.WECHAT_MOCK else wechat.oauth_url(redirect_uri, state),
            "state": state,
            "mock": wechat.WECHAT_MOCK,
        },
        "微信登录地址",
    )


@router.post("/wechat/login", summary="微信扫码免密登录（绑定后；未绑定返回临时令牌引导注册）")
def wechat_login(code: str, request: Request, db: Session = Depends(get_db)):
    try:
        sess = wechat.code2session(code)
    except Exception as e:
        raise BizError(str(e))
    bind = db.query(WechatBinding).filter(WechatBinding.openid == sess["openid"]).first()
    if not bind:
        # 未绑定：签发 10 分钟临时令牌，引导绑定学号创建账号
        wechat_token = create_wechat_token(
            sess["openid"],
            {"unionid": sess["unionid"], "nickname": sess["nickname"], "avatar": sess["avatar"]},
        )
        return ok(
            {"need_bind": True, "wechat_token": wechat_token,
             "nickname": sess["nickname"], "avatar": sess["avatar"]},
            "该微信尚未绑定账号，请绑定学号创建账号",
        )
    user = db.get(User, bind.user_id)
    if not user:
        raise BizError("绑定账号不存在", 404)
    if user.status != "active":
        raise BizError("账号已被禁用，请联系教务处")
    touch_login(user, db)
    write_log(db, user.id, "wechat_login", f"user:{user.id}", request=request)
    return ok({**_wechat_token(user), "user": _user_out(db, user)}, "微信登录成功")


@router.post("/wechat/register", summary="微信注册：首次微信登录未绑定时，绑定学号创建账号")
def wechat_register(body: WechatRegisterIn, request: Request, db: Session = Depends(get_db)):
    payload = decode_token(body.wechat_token)
    if not payload or payload.get("type") != "wechat":
        raise BizError("微信授权已过期，请重新扫码登录", 401)
    openid = payload.get("sub", "")
    if not openid:
        raise BizError("微信授权信息无效", 401)
    if db.query(WechatBinding).filter(WechatBinding.openid == openid).first():
        raise BizError("该微信已绑定其他账号")

    enc_no = encrypt_field(body.student_no)
    if db.query(User).filter(User.student_no == enc_no).first():
        raise BizError("该学号已注册，请直接用学号登录后在「个人中心」绑定微信")
    enc_phone = encrypt_field(body.phone)
    if db.query(User).filter(User.phone == enc_phone).first():
        raise BizError("该手机号已绑定其他账号")

    init_score = params.get_param(db, "credit_init", 80)
    user = User(
        student_no=enc_no,
        name=body.name,
        nickname=body.name,
        phone=enc_phone,
        password_hash=hash_password(body.password),
        college=body.college,
        role=ROLE_STUDENT,
        credit_score=init_score,
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()
    db.add(
        WechatBinding(
            user_id=user.id,
            openid=openid,
            unionid=payload.get("unionid", ""),
            nickname=payload.get("nickname", ""),
            avatar=payload.get("avatar", ""),
        )
    )
    db.commit()
    credit.change_credit(db, user.id, 0, "register", "user", user.id)
    write_log(db, user.id, "wechat_register", f"user:{user.id}", after=body.student_no, request=request)
    db.commit()
    return ok({**_wechat_token(user), "user": _user_out(db, user)}, "微信注册成功，已绑定学号")


@router.post("/wechat/bind", summary="绑定微信（需已登录）")
def wechat_bind(code: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        sess = wechat.code2session(code)
    except Exception as e:
        raise BizError(str(e))
    if db.query(WechatBinding).filter(WechatBinding.openid == sess["openid"]).first():
        raise BizError("该微信已绑定其他账号")
    if db.query(WechatBinding).filter(WechatBinding.user_id == user.id).first():
        raise BizError("当前账号已绑定微信，请先解绑")
    db.add(
        WechatBinding(
            user_id=user.id,
            openid=sess["openid"],
            unionid=sess["unionid"],
            nickname=sess["nickname"],
            avatar=sess["avatar"],
        )
    )
    db.commit()
    write_log(db, user.id, "wechat_bind", f"user:{user.id}", request=request)
    return ok({"bound": True, "nickname": sess["nickname"]}, "微信绑定成功，之后可扫码免密登录")


@router.post("/wechat/unbind", summary="解绑微信")
def wechat_unbind(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bind = db.query(WechatBinding).filter(WechatBinding.user_id == user.id).first()
    if bind:
        db.delete(bind)
        db.commit()
    return ok({"bound": False}, "已解绑微信")


@router.get("/wechat/status", summary="当前账号微信绑定状态")
def wechat_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bind = db.query(WechatBinding).filter(WechatBinding.user_id == user.id).first()
    return ok({"bound": bool(bind), "nickname": bind.nickname if bind else "",
              "avatar": bind.avatar if bind else ""})


@router.get("/me")
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ok(_user_out(db, user))


@router.put("/me")
def update_me(
    nickname: str = "",
    avatar: str = "",
    college: str = "",
    point_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """个人中心：昵称/头像/学院/交接点偏好设置"""
    if nickname:
        user.nickname = nickname
    if avatar:
        user.avatar = avatar
    if college:
        user.college = college
    if point_id:
        user.point_id = point_id
    db.commit()
    return ok(_user_out(db, user), "已更新")


@router.get("/credit", summary="信用分详情")
def credit_detail(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = credit.credit_detail(db, user.id)
    return ok(
        {
            "score": user.credit_score,
            "level": credit.level_of(user.credit_score),
            "can_publish": credit.can_publish(db, user),
            "logs": rows,
        }
    )


@router.get("/dashboard", summary="个人中心聚合：我的发布/预约/订单/评价")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    listings = (
        db.query(Listing).filter(Listing.seller_id == user.id).order_by(Listing.id.desc()).limit(50).all()
    )
    orders = (
        db.query(Order)
        .filter((Order.buyer_id == user.id) | (Order.seller_id == user.id))
        .order_by(Order.id.desc())
        .limit(50)
        .all()
    )
    wanteds = db.query(Wanted).filter(Wanted.user_id == user.id).all()
    reviews = db.query(Review).filter(Review.target_id == user.id).order_by(Review.id.desc()).limit(20).all()
    favs = db.query(Favorite).filter(Favorite.user_id == user.id).count()

    # 批量加载关联实体，避免逐条 N+1
    listing_books = load_map(db, Book, (l.book_id for l in listings))
    order_listings = load_map(db, Listing, (o.listing_id for o in orders))
    order_books = load_map(db, Book, (l.book_id for l in order_listings.values()))
    peers = load_map(db, User, [o.seller_id if o.buyer_id == user.id else o.buyer_id for o in orders])
    wanted_books = load_map(db, Book, (w.book_id for w in wanteds))

    def _lv(l: Listing) -> dict:
        book = listing_books.get(l.book_id)
        return {
            "id": l.id,
            "title": book.title if book else "",
            "isbn": book.isbn if book else "",
            **book_visuals(book),
            "images": listing_images(l.images),
            "condition_level": l.condition_level,
            "price": l.price,
            "status": l.status,
            "created_at": l.created_at.isoformat(),
            "view_count": l.view_count,
        }

    def _od(o: Order) -> dict:
        l = order_listings.get(o.listing_id)
        book = order_books.get(l.book_id) if l else None
        peer = peers.get(o.seller_id if o.buyer_id == user.id else o.buyer_id)
        return {
            "id": o.id,
            "order_no": o.order_no,
            "title": book.title if book else "",
            "price": o.price,
            "status": o.status,
            "role": "buyer" if o.buyer_id == user.id else "seller",
            "peer": (peer.nickname or peer.name) if peer else "",
            "appoint_at": o.appoint_at.isoformat() if o.appoint_at else None,
            "verify_code": o.verify_code if o.status in ("confirmed", "pending_handoff") else "",
        }

    return ok(
        {
            "listings": [_lv(l) for l in listings],
            "orders": [_od(o) for o in orders],
            "wanteds": [
                {"id": w.id, "book_title": (wanted_books.get(w.book_id).title if wanted_books.get(w.book_id) else ""),
                 "min_condition": w.min_condition, "max_price": w.max_price, "status": w.status}
                for w in wanteds
            ],
            "reviews": [
                {"id": r.id, "avg": (r.rating_desc + r.rating_condition + r.rating_punctual) / 3,
                 "comment": r.comment, "created_at": r.created_at.isoformat()}
                for r in reviews
            ],
            "favorite_count": favs,
            "unread": notify.unread_count(db, user.id),
        }
    )


@router.get("/messages", summary="站内消息")
def messages(is_read: bool | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Message).filter(Message.user_id == user.id)
    if is_read is not None:
        q = q.filter(Message.is_read.is_(is_read))
    rows = q.order_by(Message.id.desc()).limit(100).all()
    return ok(
        {
            "unread": notify.unread_count(db, user.id),
            "items": [
                {"id": m.id, "type": m.type, "title": m.title, "content": m.content,
                 "ref_id": m.ref_id, "is_read": m.is_read, "created_at": m.created_at.isoformat()}
                for m in rows
            ],
        }
    )


@router.post("/messages/{mid}/read")
def read_message(mid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.get(Message, mid)
    if m and m.user_id == user.id:
        m.is_read = True
        db.commit()
    return ok(True)


@router.delete("/messages/{mid}", summary="删除单条消息")
def delete_message(mid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.get(Message, mid)
    if not m or m.user_id != user.id:
        raise BizError("消息不存在", 404)
    db.delete(m)
    db.commit()
    return ok(True, "已删除")


@router.delete("/messages", summary="清空全部消息")
def clear_messages(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Message).filter(Message.user_id == user.id).delete()
    db.commit()
    return ok(True, "已清空")
