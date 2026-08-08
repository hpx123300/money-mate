"""预算接口：按月度设置预算、查询当月预算与支出。"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func

from ..database import get_db
from ..deps import get_current_user
from ..models import Budget, Transaction, User
from ..schemas import BudgetCreate, BudgetRead

router = APIRouter(prefix="/api/budget", tags=["预算"])


def _spent(db: Session, user_id: int, month: str) -> float:
    """某月已支出总额。"""
    total = db.exec(
        select(func.sum(Transaction.amount)).where(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.occurred_at.startswith(month),
        )
    ).one()
    return total or 0


@router.get("/{month}", response_model=BudgetRead)
def get_budget(
    month: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询某月预算；没设置返回 0。"""
    budget = db.exec(
        select(Budget).where(Budget.user_id == current.id, Budget.month == month)
    ).first()
    return BudgetRead(
        month=month,
        amount=budget.amount if budget else 0,
        spent=_spent(db, current.id, month),
    )


@router.put("/{month}", response_model=BudgetRead)
def set_budget(
    month: str,
    data: BudgetCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """设置/更新某月预算。"""
    budget = db.exec(
        select(Budget).where(Budget.user_id == current.id, Budget.month == month)
    ).first()
    if budget:
        budget.amount = data.amount
    else:
        budget = Budget(user_id=current.id, month=month, amount=data.amount)
        db.add(budget)
    db.commit()
    db.refresh(budget)
    return BudgetRead(
        month=month,
        amount=budget.amount,
        spent=_spent(db, current.id, month),
    )
