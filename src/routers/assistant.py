from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.config import AI_HOURLY_LIMIT
from ..core.rate_limit import hit
from ..core.response import BizError, ok
from ..db import get_db
from ..schemas import AssistantIn
from ..services.assistant import reply, status

router = APIRouter(prefix="/assistant", tags=["小循选书助手"])


@router.get("/status", summary="助手可用状态及管理员配置的模型")
def assistant_status():
    return ok(status())


@router.post("/chat", summary="基于公开目录和平台规则的校园选书对话")
def chat(body: AssistantIn, request: Request, db: Session = Depends(get_db)):
    address = request.client.host if request.client else "unknown"
    if not hit("assistant:minute:" + address, 6, 60) or not hit("assistant:hour:" + address, 40, 3600):
        raise BizError("提问有点频繁，请稍后继续", 429)
    if not hit("assistant:global", AI_HOURLY_LIMIT, 3600):
        raise BizError("小循本小时的服务额度已用完，请稍后继续", 429)
    return ok(reply(db, body))
