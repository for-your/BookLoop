"""
数据库引擎与会话。SQLite 与 MySQL 8 双方言兼容。
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .core.config import DATABASE_URL, DB_DIALECT
from .models import Base

# SQLite 需关闭同线程检查；MySQL 需设置连接预检
if DB_DIALECT == "sqlite":
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, future=True)
else:
    engine = create_engine(
        DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20, future=True
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    """FastAPI 依赖：请求作用域的数据库会话"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_column(table: str, column: str, ddl_type: str) -> None:
    """轻量迁移：create_all 不会修改已存在的表，这里为老库补新列（SQLite / MySQL 通用）。"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    if any(c["name"] == column for c in insp.get_columns(table)):
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def init_db(drop: bool = False) -> None:
    """建表 + 写入默认系统参数（不写业务种子数据，种子数据见 scripts/init_data.py）"""
    if drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    # 老库补列：用户自定义交接点 / 交接点归属学院
    _ensure_column("handoff_points", "created_by", "INTEGER")
    _ensure_column("handoff_points", "college", "VARCHAR(64) DEFAULT ''")
    # 老库补列：暂存「临近超期提醒」标记
    _ensure_column("storage_items", "reminded", "BOOLEAN DEFAULT 0")

    from .core.config import DEFAULT_PARAMS
    from .models import SysParam

    db = SessionLocal()
    try:
        for k, v in DEFAULT_PARAMS.items():
            if not db.query(SysParam).filter(SysParam.param_key == k).first():
                db.add(SysParam(param_key=k, param_value=v))
        db.commit()
    finally:
        db.close()
