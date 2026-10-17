"""数据模型：一张表 = 一个 SQLModel 类。"""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Index, Numeric
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def alive() -> Column:
    """未删除的流水。所有读取 Transaction 的查询都要带上它。

    放在模型层而不是每个路由里拼条件，是因为「漏一处过滤」的后果
    是统计悄悄变多——这类 bug 不会报错，只会让数字对不上。
    """
    return Transaction.deleted_at.is_(None)


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

    # 统计接口的查询几乎都是「某用户 + 某时间段」，单列索引只能命中一半条件，
    # 复合索引能一次定位到区间，数据量上来后差别很明显。
    __table_args__ = (Index("ix_transaction_user_date", "user_id", "occurred_at"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    category_id: int = Field(index=True, foreign_key="category.id")
    wallet_id: int | None = Field(default=None, index=True, foreign_key="wallet.id")
    amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(10, 2)))
    type: str = Field(index=True)  # income / expense
    note: str = Field(default="")
    occurred_at: date = Field(default_factory=date.today, index=True)
    # 客户端生成的幂等键：双击提交或网络重试时，同一笔不会记两次
    client_token: str | None = Field(default=None, index=True, max_length=64)
    # 软删除：记错账的人常常是「按错了」，物理删除后想恢复都无从下手。
    # 查询侧统一带 deleted_at.is_(None) 过滤。
    deleted_at: datetime | None = Field(default=None)
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


class UserFact(SQLModel, table=True):
    """长期记忆：用户的结构性事实（收入模式 / 固定支出 / 偏好）。

    刻意不用向量库：这类事实需要精确匹配和聚合计算，
    「每月 1 号到账 2000」塞进向量库里反而查不准。
    """

    __table_args__ = (
        Index("ix_userfact_user_kind_key", "user_id", "kind", "key", unique=True),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    kind: str = Field(max_length=24)  # income_pattern / fixed_expense / preference / other
    key: str = Field(max_length=40)
    value: str = Field(max_length=200)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
