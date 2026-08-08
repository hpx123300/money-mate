"""数据库模块：SQLModel + SQLite（生产可换 MySQL，只改一行配置）。"""

from sqlmodel import SQLModel, Session, create_engine

from .config import settings

# SQLite 需要这个参数允许跨线程访问（FastAPI 线程池）
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    echo=settings.app_env == "dev",  # 开发时打印 SQL，方便学习
    connect_args=connect_args,
)


def init_db() -> None:
    """启动时自动建表（小项目够用；生产建议用 Alembic 迁移）。"""
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_db():
    """FastAPI 依赖：每个请求一个数据库会话，请求结束自动关闭。"""
    with Session(engine) as session:
        yield session

