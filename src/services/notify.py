"""
通知服务：站内信 + WebSocket 实时推送 + 短信/邮件抽象接口。
需求：通知渠道（站内信／短信／邮件）抽象为统一接口，便于后续接入企业微信；
站内消息采用 WebSocket 实时推送；短信仅用于关键节点，单用户每日上限 5 条。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import USE_REDIS
from ..models import Message
from . import params


# ------------------------- WebSocket 连接管理 -------------------------
class WSManager:
    """极简 WebSocket 广播器（生产可替换为 Redis Pub/Sub）"""

    def __init__(self) -> None:
        self._connections: dict[int, Any] = {}

    async def connect(self, user_id: int, ws: Any) -> None:
        self._connections[user_id] = ws

    def disconnect(self, user_id: int) -> None:
        self._connections.pop(user_id, None)

    async def send(self, user_id: int, payload: dict) -> None:
        ws = self._connections.get(user_id)
        if ws is None:
            return
        try:
            await ws.send_json(payload)
        except Exception:
            self.disconnect(user_id)


ws_manager = WSManager()

# Redis（可选）：启用后用于会话与限流
redis_client = None
if USE_REDIS:
    try:
        import redis  # type: ignore

        from ..core.config import REDIS_URL

        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        redis_client = None


# ------------------------- 短信网关（可插拔） -------------------------
class SMSProvider:
    """默认实现为日志打印；接入学校短信网关时替换 send 方法即可。"""

    def send(self, phone: str, content: str) -> bool:
        print(f"[SMS] -> {phone}: {content}")
        return True


sms_provider = SMSProvider()


def sms_today_count(db: Session, user_id: int) -> int:
    # 今日已通过 Message 渠道标记发送的短信量（简化统计：type=sms）
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(func.count(Message.id))
        .filter(Message.user_id == user_id, Message.type == "sms", Message.created_at >= today)
        .scalar()
        or 0
    )


def notify(
    db: Session,
    user_id: int,
    title: str,
    content: str,
    type: str = "system",
    ref_id: int | None = None,
    send_sms: bool = False,
    phone: str | None = None,
) -> Message:
    """统一通知入口：写站内信 → 触发 WebSocket 推送 → 可选短信"""
    msg = Message(
        user_id=user_id,
        type=type,
        title=title,
        content=content,
        ref_id=ref_id,
    )
    db.add(msg)
    db.flush()

    # WebSocket 实时推送（异步环境下由调用方 await push_ws）
    try:
        import asyncio

        asyncio.get_running_loop().create_task(
            ws_manager.send(
                user_id,
                {"type": type, "title": title, "content": content, "ref_id": ref_id},
            )
        )
    except RuntimeError:
        pass  # 无事件循环（如脚本环境）时跳过

    if send_sms and phone:
        limit = params.get_param(db, "sms_daily_limit", 5)
        if sms_today_count(db, user_id) < limit:
            if sms_provider.send(phone, content):
                db.add(
                    Message(user_id=user_id, type="sms", title=title, content=content, ref_id=ref_id)
                )
                db.flush()
    return msg


def unread_count(db: Session, user_id: int) -> int:
    return (
        db.query(func.count(Message.id))
        .filter(Message.user_id == user_id, Message.is_read.is_(False))
        .scalar()
        or 0
    )
