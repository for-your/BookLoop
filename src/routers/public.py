"""公共接口：健康检查、图片上传、WebSocket 实时消息。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..core.response import BizError, ok
from ..core.security import decode_token
from ..db import get_db
from ..services.notify import ws_manager
from ..services.storage import UploadError, save_image

router = APIRouter(tags=["公共"])


@router.get("/health", summary="健康检查")
def health():
    return ok({"status": "ok", "service": "campus-book-cycle"})


@router.post("/upload", summary="图片上传（jpg/png/webp，单图 ≤5MB）")
def upload(file: UploadFile = File(...)):
    try:
        url = save_image(file)
    except UploadError as e:
        raise BizError(str(e))
    return ok({"url": url}, "上传成功")


@router.websocket("/ws")
async def ws(websocket: WebSocket, token: str = "", db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=1008)
        return
    user_id = int(payload.get("sub", 0))
    await websocket.accept()
    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
