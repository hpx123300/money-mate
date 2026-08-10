"""请求/响应模型：Pydantic 负责校验，FastAPI 自动生成文档。"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, PlainSerializer

# Decimal 在 JSON 序列化时转成 float（避免输出成字符串），Python 模式下仍保留 Decimal
MoneyDecimal = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


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


# ============ AI 记账助手 ============


class AiParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class AiCategoryRequest(BaseModel):
    note: str = Field(min_length=1, max_length=200)


class AiParseResult(BaseModel):
    type: str
    amount: MoneyDecimal
    category_id: int
    category: str
    wallet_id: int | None
    wallet: str | None
    note: str
    occurred_at: date


class AiCategoryResult(BaseModel):
    category_id: int
    category: str
    type: str


class AiSummaryResult(BaseModel):
    month: str
    summary: str


# ============ 钱包 ============


class WalletCreate(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    balance: MoneyDecimal = Field(default=Decimal("0"), ge=0, description="初始余额")


class WalletRead(BaseModel):
    id: int
    name: str
    balance: MoneyDecimal = Decimal("0")  # 初始余额 + 收支累计后的实时余额
    transaction_count: int = 0


# ============ 流水 ============


class TransactionCreate(BaseModel):
    category_id: int
    wallet_id: int | None = None
    amount: MoneyDecimal = Field(gt=0, description="金额必须大于 0")
    type: str = Field(pattern="^(income|expense)$")
    note: str = Field(default="", max_length=200)
    occurred_at: date = Field(default_factory=date.today)


class TransactionUpdate(BaseModel):
    amount: MoneyDecimal | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=200)
    occurred_at: date | None = None


class TransactionRead(BaseModel):
    id: int
    category_id: int
    category_name: str = ""
    wallet_id: int | None = None
    wallet_name: str = ""
    amount: MoneyDecimal
    type: str
    note: str
    occurred_at: date


class TransactionPage(BaseModel):
    """分页返回：总数 + 当前页数据"""

    total: int
    page: int
    page_size: int
    items: list[TransactionRead]


class ImportResult(BaseModel):
    """账单导入结果"""

    total_rows: int
    imported: int
    skipped_duplicates: int
    failed: int
    errors: list[str] = []


# ============ 预算 ============


class BudgetCreate(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$", description="格式：2026-08")
    amount: MoneyDecimal = Field(gt=0)


class BudgetRead(BaseModel):
    month: str
    amount: MoneyDecimal
    spent: MoneyDecimal = Decimal("0")  # 该月已支出


class AllowanceRead(BaseModel):
    """生活费规划（含实时计算）"""

    amount: MoneyDecimal              # 每月生活费
    day_of_month: int          # 每月几号到账
    spent: MoneyDecimal = Decimal("0")           # 本月已花
    remaining: MoneyDecimal = Decimal("0")       # 本月剩余
    days_left: int = 0         # 距离下月生活费到账还有几天
    daily_budget: MoneyDecimal = Decimal("0")    # 日均可用 = 剩余 / 剩余天数


class AllowanceWrite(BaseModel):
    amount: MoneyDecimal = Field(gt=0)
    day_of_month: int = Field(ge=1, le=28)


# ============ 统计 ============


class CategoryStat(BaseModel):
    category_id: int
    category_name: str
    total: MoneyDecimal
    percent: float  # 占该类型总额的百分比


class MonthSummary(BaseModel):
    month: str
    total_income: MoneyDecimal
    total_expense: MoneyDecimal
    balance: MoneyDecimal
    income_by_category: list[CategoryStat] = []
    expense_by_category: list[CategoryStat] = []


class TrendPoint(BaseModel):
    month: str
    income: MoneyDecimal
    expense: MoneyDecimal


class TrendOut(BaseModel):
    points: list[TrendPoint]


class MonthlySummary(BaseModel):
    """月度总结：用规则拼出的一段人话（不调 LLM，零成本）"""

    month: str
    text: str


class AnnualMonthPoint(BaseModel):
    month: str  # 2026-01
    income: MoneyDecimal
    expense: MoneyDecimal


class AnnualReport(BaseModel):
    """年度账单报告：像支付宝年度账单那样的数据叙事"""

    year: int
    total_income: MoneyDecimal
    total_expense: MoneyDecimal
    balance: MoneyDecimal
    expense_by_category: list[CategoryStat] = []
    monthly: list[AnnualMonthPoint] = []
    biggest_expense: str = ""     # 最大单笔描述
    busiest_weekday: str = ""     # 花钱最多的星期几
    fun_facts: list[str] = []     # 彩蛋：奶茶点了几次等
    summary: str = ""             # 年度总结一段话
