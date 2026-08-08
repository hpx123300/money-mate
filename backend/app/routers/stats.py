"""统计接口：月度汇总 + 趋势。"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from ..database import get_db
from ..deps import get_current_user
from ..models import Budget, Category, Transaction, User
from ..schemas import CategoryStat, MonthSummary, MonthlySummary, TrendOut, TrendPoint

router = APIRouter(prefix="/api/stats", tags=["统计"])


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _prev_months(n: int, current: str) -> list[str]:
    """返回当前月往前 n 个月的月份列表（含当前月）。"""
    y, m = int(current[:4]), int(current[5:7])
    months = []
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(months))


@router.get("/summary", response_model=MonthSummary)
def month_summary(
    month: str | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """某月收支汇总：总额 + 各分类占比（month 缺省为当月）。"""
    month = month or _month_key(date.today())
    query = select(Transaction).where(
        Transaction.user_id == current.id,
        Transaction.occurred_at.startswith(month),
    )
    rows = db.exec(query).all()

    cats = {
        c.id: c.name
        for c in db.exec(select(Category).where(Category.user_id == current.id)).all()
    }
    total_income = sum(t.amount for t in rows if t.type == "income")
    total_expense = sum(t.amount for t in rows if t.type == "expense")

    def by_category(ctype: str, total: float) -> list[CategoryStat]:
        groups: dict[int, float] = {}
        for t in rows:
            if t.type == ctype:
                groups[t.category_id] = groups.get(t.category_id, 0) + t.amount
        return [
            CategoryStat(
                category_id=cid,
                category_name=cats.get(cid, "未知"),
                total=amount,
                percent=round(amount / total * 100, 1) if total else 0,
            )
            for cid, amount in sorted(groups.items(), key=lambda x: -x[1])
        ]

    return MonthSummary(
        month=month,
        total_income=round(total_income, 2),
        total_expense=round(total_expense, 2),
        balance=round(total_income - total_expense, 2),
        income_by_category=by_category("income", total_income),
        expense_by_category=by_category("expense", total_expense),
    )


@router.get("/trend", response_model=TrendOut)
def month_trend(
    months: int = 6,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """近 N 个月的收支趋势（折线图数据）。"""
    months = max(2, min(months, 12))
    current_month = _month_key(date.today())
    wanted = _prev_months(months, current_month)

    # 一次性查出所有月份数据，再按月份分组（避免 N 次查询）
    rows = db.exec(
        select(Transaction).where(
            Transaction.user_id == current.id,
            Transaction.occurred_at >= f"{wanted[0]}-01",
        )
    ).all()

    income_map: dict[str, float] = {}
    expense_map: dict[str, float] = {}
    for t in rows:
        key = _month_key(t.occurred_at)
        target = income_map if t.type == "income" else expense_map
        target[key] = target.get(key, 0) + t.amount

    return TrendOut(
        points=[
            TrendPoint(
                month=m,
                income=round(income_map.get(m, 0), 2),
                expense=round(expense_map.get(m, 0), 2),
            )
            for m in wanted
        ]
    )


@router.get("/monthly-summary", response_model=MonthlySummary)
def monthly_summary(
    month: str | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    月度总结：纯规则生成的一段「人话」。
    亮点：统计奶茶/咖啡/外卖次数，月底给一句生活化总结。
    不用 LLM，零成本，逻辑完全可解释。
    """
    month = month or _month_key(date.today())
    rows = db.exec(
        select(Transaction).where(
            Transaction.user_id == current.id,
            Transaction.occurred_at.startswith(month),
        )
    ).all()
    cats = {
        c.id: c.name
        for c in db.exec(select(Category).where(Category.user_id == current.id)).all()
    }

    income = sum(t.amount for t in rows if t.type == "income")
    expense = sum(t.amount for t in rows if t.type == "expense")
    balance = income - expense

    lines = [f"{month} 月度总结"]

    # 收支总览
    lines.append(f"总收入 ¥{income:.2f}，总支出 ¥{expense:.2f}，结余 ¥{balance:.2f}。")

    # 支出最多的分类
    by_cat: dict[str, float] = {}
    for t in rows:
        if t.type == "expense":
            name = cats.get(t.category_id, "其他")
            by_cat[name] = by_cat.get(name, 0) + t.amount
    if by_cat:
        top_name, top_amount = max(by_cat.items(), key=lambda x: x[1])
        top_percent = top_amount / expense * 100 if expense else 0
        lines.append(f"花钱最多的是「{top_name}」，¥{top_amount:.2f}，占支出的 {top_percent:.0f}%。")

    # 最大单笔
    expenses = [t for t in rows if t.type == "expense"]
    if expenses:
        biggest = max(expenses, key=lambda t: t.amount)
        note = f"（{biggest.note}）" if biggest.note else ""
        lines.append(
            f"最大一笔是「{cats.get(biggest.category_id, '其他')}」¥{biggest.amount:.2f}{note}，发生在 {biggest.occurred_at}。"
        )

    # 奶茶/咖啡/外卖彩蛋
    for keyword in ("奶茶", "咖啡", "外卖"):
        hits = [t for t in expenses if keyword in t.note]
        if hits:
            total = sum(t.amount for t in hits)
            lines.append(f"{keyword}点了 {len(hits)} 次，共花了 ¥{total:.2f}。")

    # 预算情况
    budget = db.exec(
        select(Budget).where(Budget.user_id == current.id, Budget.month == month)
    ).first()
    if budget and budget.amount > 0:
        left = budget.amount - expense
        if left < 0:
            lines.append(f"预算 ¥{budget.amount:.2f}，超支了 ¥{-left:.2f}，下个月注意！")
        else:
            lines.append(f"预算 ¥{budget.amount:.2f}，还剩 ¥{left:.2f}，控制得不错。")

    # 结尾一句话
    if expense == 0 and income == 0:
        lines.append("这个月还没有记账，从今天开始吧！")
    elif balance < 0:
        lines.append("支出超过收入啦，看看哪块能省一省。")
    else:
        lines.append("总体健康，继续保持！")

    return MonthlySummary(month=month, text="\n".join(lines))
