"""数据库模块：SQLModel + SQLite（生产可换 MySQL，只改一行配置）。"""

import os

from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine, select, update

from .config import settings
from .models import Transaction, User, Wallet

# SQLite 需要这个参数允许跨线程访问（FastAPI 线程池）
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# 确保数据目录存在（SQLite 文件默认放这里）
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

engine = create_engine(
    settings.database_url,
    echo=settings.app_env == "dev",  # 开发时打印 SQL，方便学习
    connect_args=connect_args,
)


def init_db() -> None:
    """启动时自动建表，并做一次轻量迁移（新增字段/默认钱包）。"""
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    _migrate()
    _ensure_default_wallets()


def _migrate() -> None:
    """
    轻量迁移：给旧版本已有的 transaction 表补上 wallet_id 列。
    生产项目应该用 Alembic 管理迁移，这里是教学项目的最小实现。
    """
    with engine.begin() as conn:
        cols = {
            row[1]
            for row in conn.execute(text('PRAGMA table_info("transaction")')).fetchall()
        }
        if "wallet_id" not in cols:
            conn.execute(
                text('ALTER TABLE "transaction" ADD COLUMN wallet_id INTEGER REFERENCES wallet(id)')
            )
            print("[迁移] transaction 表已补充 wallet_id 列")


def _ensure_default_wallets() -> None:
    """
    给还没有钱包的用户创建一个「现金」钱包，
    并把该用户历史流水归到这个钱包下（数据不丢）。
    """
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        changed = False
        for user in users:
            wallet = session.exec(
                select(Wallet).where(Wallet.user_id == user.id)
            ).first()
            if wallet:
                continue
            wallet = Wallet(user_id=user.id, name="现金", balance=0)
            session.add(wallet)
            session.flush()
            session.exec(
                update(Transaction)
                .where(
                    Transaction.user_id == user.id,
                    Transaction.wallet_id.is_(None),
                )
                .values(wallet_id=wallet.id)
            )
            changed = True
        if changed:
            session.commit()
            print("[迁移] 已为用户创建默认钱包并归入历史流水")


def get_db():
    """FastAPI 依赖：每个请求一个数据库会话，请求结束自动关闭。"""
    with Session(engine) as session:
        yield session
