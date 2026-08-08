"""数据模型：一张表 = 一个 SQLModel 类。"""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=32)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=utcnow)


class Category(SQLModel, table=True):
    """收支分类：支出（餐饮/交通/购物…）或收入（工资/兼职/理财…）"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    name: str
    type: str = Field(index=True)  # income / expense
    created_at: datetime = Field(default_factory=utcnow)


class Transaction(SQLModel, table=True):
    """一笔收支记录"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    category_id: int = Field(index=True, foreign_key="category.id")
    amount: float = Field(default=0)
    type: str = Field(index=True)  # income / expense
    note: str = Field(default="")
    occurred_at: date = Field(default_factory=date.today, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Budget(SQLModel, table=True):
    """月度预算：每个用户每个月一条"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    month: str = Field(index=True)  # 格式：2026-08
    amount: float = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow)
