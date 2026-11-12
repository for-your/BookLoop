"""
校园二手教材循环平台 —— FastAPI 应用入口
按路由分组划分为八个业务模块（单体部署）：
用户认证、教材目录、挂牌、匹配、订单、交接、信用、统计
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import API_PREFIX, APP_NAME, UPLOAD_DIR, PROJECT_ROOT
from .core.response import BizError
from .db import init_db
from .routers import admin, assistant, auth, catalog, handoff, listings, orders, public, reviews, search
from .services import scheduler
from .services.book_discovery import COVER_DIR

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(title=APP_NAME, version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

# 跨域（前后端分离部署时按需收紧 allow_origins）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"code": exc.status_code, "msg": exc.detail, "data": None})


@app.exception_handler(BizError)
async def biz_exc_handler(request: Request, exc: BizError):
    return JSONResponse(status_code=exc.http_status, content={"code": exc.http_status, "msg": exc.msg, "data": None})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # 错误码对用户不可见，统一提示
    return JSONResponse(status_code=500, content={"code": 500, "msg": "服务器开小差了，请稍后重试", "data": None})


for router in (public.router, auth.router, catalog.router, listings.router, search.router,
               orders.router, handoff.router, reviews.router, admin.router, assistant.router):
    app.include_router(router, prefix=API_PREFIX)

# 上传文件静态目录
app.mount("/static/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static/covers", StaticFiles(directory=str(COVER_DIR)), name="covers")

# 前端挂载放在最后，避免根路径托管抢先匹配 /api 和 /static。
app.mount("/", StaticFiles(directory=str(PROJECT_ROOT / "web"), html=True), name="frontend")
