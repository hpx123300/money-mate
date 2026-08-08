"""请求/响应模型：Pydantic 负责校验，FastAPI 自动生成文档。"""

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


# ============ 用户 ============


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=6, max_length=64)


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ============ 分类 ============


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    type: str = Field(pattern="^(income|expense)$")


class CategoryRead(BaseModel):
    id: int
    name: str
    type: str


# ============ 钱包 ============


class WalletCreate(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    balance: float = Field(default=0, ge=0, description="初始余额")


class WalletRead(BaseModel):
    id: int
    name: str
    balance: float = 0  # 初始余额 + 收支累计后的实时余额
    transaction_count: int = 0


# ============ 流水 ============


class TransactionCreate(BaseModel):
    category_id: int
    wallet_id: int | None = None
    amount: float = Field(gt=0, description="金额必须大于 0")
    type: str = Field(pattern="^(income|expense)$")
    note: str = Field(default="", max_length=200)
    occurred_at: date = Field(default_factory=date.today)


class TransactionUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=200)
    occurred_at: date | None = None


class TransactionRead(BaseModel):
    id: int
    category_id: int
    category_name: str = ""
    wallet_id: int | None = None
    wallet_name: str = ""
    amount: float
    type: str
    note: str
    occurred_at: date


# ============ 预算 ============


class BudgetCreate(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$", description="格式：2026-08")
    amount: float = Field(gt=0)


class BudgetRead(BaseModel):
    month: str
    amount: float
    spent: float = 0  # 该月已支出


# ============ 统计 ============


class CategoryStat(BaseModel):
    category_id: int
    category_name: str
    total: float
    percent: float  # 占该类型总额的百分比


class MonthSummary(BaseModel):
    month: str
    total_income: float
    total_expense: float
    balance: float
    income_by_category: list[CategoryStat] = []
    expense_by_category: list[CategoryStat] = []


class TrendPoint(BaseModel):
    month: str
    income: float
    expense: float


class TrendOut(BaseModel):
    points: list[TrendPoint]


class MonthlySummary(BaseModel):
    """月度总结：用规则拼出的一段人话（不调 LLM，零成本）"""

    month: str
    text: str
