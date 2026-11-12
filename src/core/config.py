"""
全局配置中心。
- 默认使用 SQLite + 本地文件存储 + 内存缓存，无需额外数据库服务；
- 通过设置环境变量即可切换到需求文档要求的 MySQL 8 / Redis 7 / MinIO(S3) 生产环境。
所有业务阈值均来自 system_params 表（可后台配置），此处的常量仅作为兜底默认值。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# src/core/config.py -> src -> 仓库根
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "configs"
ENV_FILE = Path(os.getenv("BOOKLOOP_ENV_FILE", str(CONFIG_DIR / ".env")))
if not ENV_FILE.is_absolute():
    ENV_FILE = PROJECT_ROOT / ENV_FILE
# 系统环境变量优先于 configs/.env，便于容器和 CI 注入生产配置。
load_dotenv(ENV_FILE, override=False)

SEED_DIR = PROJECT_ROOT / "data" / "seed"
DATA_DIR = Path(os.getenv("BOOKLOOP_DATA_DIR", str(PROJECT_ROOT / "data")))
if not DATA_DIR.is_absolute():
    DATA_DIR = PROJECT_ROOT / DATA_DIR
DATA_DIR = DATA_DIR.resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# ------------------------------ 基础 ------------------------------
APP_NAME = "校园二手教材循环平台"
API_PREFIX = "/api"
DEBUG = _env_bool("DEBUG", True)

# ------------------------------ 数据库 ------------------------------
# DB_DIALECT: sqlite | mysql
DB_DIALECT = _env("DB_DIALECT", "sqlite").lower()
MYSQL_HOST = _env("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = _env("MYSQL_PORT", "3306")
MYSQL_USER = _env("MYSQL_USER", "root")
MYSQL_PASSWORD = _env("MYSQL_PASSWORD", "root123456")
MYSQL_DB = _env("MYSQL_DB", "bookcycle")

if DB_DIALECT == "mysql":
    DATABASE_URL = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
    )
else:
    DATABASE_URL = f"sqlite:///{DATA_DIR.as_posix()}/app.db"

# ------------------------------ Redis ------------------------------
USE_REDIS = _env_bool("USE_REDIS", False)
REDIS_URL = _env("REDIS_URL", "redis://127.0.0.1:6379/0")

# ------------------------------ 对象存储 ------------------------------
# STORAGE: local | s3
STORAGE_TYPE = _env("STORAGE_TYPE", "local").lower()
S3_ENDPOINT = _env("S3_ENDPOINT", "http://127.0.0.1:9000")
S3_ACCESS_KEY = _env("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = _env("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = _env("S3_BUCKET", "bookcycle")
S3_REGION = _env("S3_REGION", "us-east-1")
PUBLIC_BASE_URL = _env("PUBLIC_BASE_URL", "")

# ------------------------------ 安全 ------------------------------
SECRET_KEY = _env("SECRET_KEY", "campus-book-cycle-dev-secret-key-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(_env("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))  # 需求：2 小时
REFRESH_TOKEN_EXPIRE_DAYS = int(_env("REFRESH_TOKEN_EXPIRE_DAYS", "7"))       # 需求：7 天

# AES-256 字段加密密钥（学号、手机号）。生产环境务必通过环境变量注入。
_KEY_FILE = DATA_DIR / ".aes_key"
if os.getenv("AES_KEY"):
    AES_KEY = os.getenv("AES_KEY", "").encode()[:32].ljust(32, b"0")
else:
    if _KEY_FILE.exists():
        AES_KEY = _KEY_FILE.read_bytes()[:32]
    else:
        import secrets
        AES_KEY = secrets.token_bytes(32)
        _KEY_FILE.write_bytes(AES_KEY)

# ------------------------------ 微信登录 ------------------------------
# WECHAT_MODE: mp_h5=公众号网页授权（微信内置浏览器）| open_qr=开放平台网站扫码登录
WECHAT_APPID = _env("WECHAT_APPID", "")
WECHAT_SECRET = _env("WECHAT_SECRET", "")
WECHAT_MODE = _env("WECHAT_MODE", "mp_h5").lower()
WECHAT_REDIRECT_URI = _env("WECHAT_REDIRECT_URI", "http://127.0.0.1:8000/")
# 未配置 AppID/Secret 时自动进入演示模式（code="demo" 免密登录预置演示账号）
WECHAT_MOCK = _env_bool("WECHAT_MOCK", not (bool(WECHAT_APPID) and bool(WECHAT_SECRET)))

AI_ENABLED = _env_bool("AI_ENABLED", True)
AI_BASE_URL = _env("AI_BASE_URL", "https://token.sensenova.cn/v1").strip().rstrip("/")
AI_API_KEY = _env("AI_API_KEY", "").strip()
AI_MODEL = _env("AI_MODEL", "deepseek-flash").strip() or "deepseek-flash"
AI_FALLBACK_MODEL = _env("AI_FALLBACK_MODEL").strip()
_ai_models = [AI_MODEL, AI_FALLBACK_MODEL, *_env("AI_MODELS").split(",")]
AI_MODELS = tuple(dict.fromkeys(model.strip() for model in _ai_models if model.strip()))
AI_MAX_TOKENS = min(8192, max(512, int(_env("AI_MAX_TOKENS", "4096"))))
AI_TIMEOUT_SECONDS = min(60, max(5, int(_env("AI_TIMEOUT_SECONDS", "45"))))
AI_HOURLY_LIMIT = max(1, int(_env("AI_HOURLY_LIMIT", "100")))

# ------------------------------ 业务兜底阈值 ------------------------------
# 实际运行以 system_params 表为准，见 src/services/params.py
DEFAULT_PARAMS = {
    "price_ratio_max": "0.70",        # 挂牌价不得超过原价的 70%
    "price_ratio_min_suggest": "0.30",
    "max_on_sale_per_user": "20",     # 单用户在架上限
    "max_same_isbn_per_user": "3",    # 同一 ISBN 在架上限
    "listing_valid_days": "90",       # 挂牌有效期
    "reserve_lock_hours": "24",       # 预约锁定 24 小时
    "confirm_timeout_hours": "24",    # 卖方 24 小时未确认自动释放
    "max_reschedule": "2",           # 最多改约 2 次
    "cancel_penalty": "5",           # 单方取消违约扣分
    "cancel_penalty_urgent": "10",   # 临近交接 2 小时内取消
    "cancel_urgent_hours": "2",
    "order_overtime_hours": "48",    # 超时未核销自动关闭
    "overtime_penalty": "3",         # 超时双方各扣
    "slot_capacity": "20",           # 单时段容量
    "storage_days": "7",             # 暂存 7 日
    "credit_init": "80",
    "credit_max": "100",
    "credit_deal_add": "2",
    "credit_good_add": "1",
    "credit_bad_sub": "3",
    "credit_break_sub": "5",
    "credit_appeal_lose_sub": "10",
    "credit_publish_min": "60",      # 低于此分禁止发布
    "idle_months_offline": "12",     # 12 个月未登录自动下架
    "sms_daily_limit": "5",
}

# 成色 6 档（可配置）
CONDITION_LEVELS = ["全新", "九五新", "九成新", "八成新", "七成新", "有破损"]

# 角色
ROLE_STUDENT = "student"
ROLE_POINT_ADMIN = "point_admin"
ROLE_PLATFORM_ADMIN = "admin"
