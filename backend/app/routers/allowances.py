"""
生活费规划接口（大学生场景的核心特色）。

逻辑：设置每月生活费金额和到账日后，自动计算——
- 本月已花 / 剩余
- 距离下月生活费到账还有几天
- 日均可用 = 剩余 / 剩余天数（这就是"钱还能撑几天"的答案）
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_db
from ..deps import get_current_user
from ..models import Allowance, Transaction, User
from ..schemas import AllowanceRead, AllowanceWrite

router = APIRouter(prefix="/api/allowance", tags=["生活费"])


def _month_spent(db: Session, user_id: int) -> Decimal:
    today = date.today()
    month = f"{today.year:04d}-{today.month:02d}"
    rows = db.exec(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.occurred_at.startswith(month),
        )
    ).all()
    return round(sum((t.amount for t in rows), Decimal("0")), 2)


def _next_arrival(today: date, day_of_month: int) -> date:
    """下一次生活费到账日期。"""
    if today.day < day_of_month:
        return date(today.year, today.month, day_of_month)
    next_month = today.month % 12 + 1
    next_year = today.year + (1 if today.month == 12 else 0)
    return date(next_year, next_month, day_of_month)


def _read(db: Session, allowance: Allowance, user_id: int) -> AllowanceRead:
    today = date.today()
    spent = _month_spent(db, user_id)
    remaining = round(allowance.amount - spent, 2)
    days_left = (_next_arrival(today, allowance.day_of_month) - today).days
    daily = round(remaining / days_left, 2) if days_left > 0 else remaining
    return AllowanceRead(
        amount=allowance.amount,
        day_of_month=allowance.day_of_month,
        spent=spent,
        remaining=remaining,
        days_left=days_left,
        daily_budget=daily,
    )


@router.get("", response_model=AllowanceRead)
def get_allowance(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询生活费规划；没设置过返回全 0。"""
    allowance = db.exec(
        select(Allowance).where(Allowance.user_id == current.id)
    ).first()
    if allowance is None:
        return AllowanceRead(amount=Decimal("0"), day_of_month=1, spent=_month_spent(db, current.id))
    return _read(db, allowance, current.id)


@router.put("", response_model=AllowanceRead)
def set_allowance(
    data: AllowanceWrite,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """设置/更新每月生活费与到账日。"""
    allowance = db.exec(
        select(Allowance).where(Allowance.user_id == current.id)
    ).first()
    if allowance:
        allowance.amount = data.amount
        allowance.day_of_month = data.day_of_month
    else:
        allowance = Allowance(
            user_id=current.id,
            amount=data.amount,
            day_of_month=data.day_of_month,
        )
        db.add(allowance)
    db.commit()
    db.refresh(allowance)
    return _read(db, allowance, current.id)
