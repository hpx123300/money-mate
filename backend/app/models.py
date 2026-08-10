"""数据模型：一张表 = 一个 SQLModel 类。"""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=32)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=utcnow)


class Wallet(SQLModel, table=True):
    """钱包/账户：微信、支付宝、现金…… 每笔流水记在某个钱包下"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    name: str = Field(max_length=20)
    balance: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(10, 2)), description="初始余额（之后收支自动累计）")
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
    wallet_id: int | None = Field(default=None, index=True, foreign_key="wallet.id")
    amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(10, 2)))
    type: str = Field(index=True)  # income / expense
    note: str = Field(default="")
    occurred_at: date = Field(default_factory=date.today, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Budget(SQLModel, table=True):
    """月度预算：每个用户每个月一条"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    month: str = Field(index=True)  # 格式：2026-08
    amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(10, 2)))
    created_at: datetime = Field(default_factory=utcnow)


class Allowance(SQLModel, table=True):
    """生活费设置：大学生每月生活费金额 + 到账日（每个用户一条）"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, unique=True, foreign_key="user.id")
    amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(10, 2)))
    day_of_month: int = Field(default=1, ge=1, le=28)  # 每月几号到账
    created_at: datetime = Field(default_factory=utcnow)
