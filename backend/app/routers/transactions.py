"""流水接口：增删改查 + 筛选 + CSV 导出。"""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from ..database import get_db
from ..deps import get_current_user
from ..models import Category, Transaction, User
from ..schemas import TransactionCreate, TransactionRead, TransactionUpdate

router = APIRouter(prefix="/api/transactions", tags=["流水"])


def _to_read(t: Transaction, categories: dict[int, str]) -> TransactionRead:
    return TransactionRead(
        id=t.id,
        category_id=t.category_id,
        category_name=categories.get(t.category_id, ""),
        amount=t.amount,
        type=t.type,
        note=t.note,
        occurred_at=t.occurred_at,
    )


def _category_names(db: Session, user_id: int) -> dict[int, str]:
    return {
        c.id: c.name
        for c in db.exec(select(Category).where(Category.user_id == user_id)).all()
    }


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    month: str | None = None,      # 2026-08
    type: str | None = None,       # income / expense
    category_id: int | None = None,
    keyword: str | None = None,    # 备注关键词搜索
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """流水列表，支持按月份/类型/分类筛选。"""
    query = select(Transaction).where(Transaction.user_id == current.id)
    if month:
        query = query.where(Transaction.occurred_at.startswith(month))
    if type:
        query = query.where(Transaction.type == type)
    if category_id:
        query = query.where(Transaction.category_id == category_id)
    if keyword:
        query = query.where(Transaction.note.contains(keyword))
    rows = db.exec(query.order_by(Transaction.occurred_at.desc(), Transaction.id.desc())).all()
    names = _category_names(db, current.id)
    return [_to_read(t, names) for t in rows]


@router.post("", response_model=TransactionRead, status_code=201)
def create_transaction(
    data: TransactionCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """记一笔：校验分类属于当前用户，且类型与分类类型一致。"""
    category = db.get(Category, data.category_id)
    if not category or category.user_id != current.id:
        raise HTTPException(status_code=400, detail="分类不存在")
    if category.type != data.type:
        raise HTTPException(status_code=400, detail="分类类型与流水类型不一致")
    t = Transaction(
        user_id=current.id,
        category_id=data.category_id,
        amount=data.amount,
        type=data.type,
        note=data.note,
        occurred_at=data.occurred_at,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_read(t, _category_names(db, current.id))


@router.put("/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改流水（金额/备注/日期）。"""
    t = db.get(Transaction, transaction_id)
    if not t or t.user_id != current.id:
        raise HTTPException(status_code=404, detail="流水不存在")
    if data.amount is not None:
        t.amount = data.amount
    if data.note is not None:
        t.note = data.note
    if data.occurred_at is not None:
        t.occurred_at = data.occurred_at
    db.add(t)
    db.commit()
    db.refresh(t)
    return _to_read(t, _category_names(db, current.id))


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(
    transaction_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = db.get(Transaction, transaction_id)
    if not t or t.user_id != current.id:
        raise HTTPException(status_code=404, detail="流水不存在")
    db.delete(t)
    db.commit()


@router.get("/export")
def export_csv(
    month: str | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出流水为 CSV（用浏览器直接下载，方便做自己的数据分析）。"""
    query = select(Transaction).where(Transaction.user_id == current.id)
    if month:
        query = query.where(Transaction.occurred_at.startswith(month))
    rows = db.exec(query.order_by(Transaction.occurred_at)).all()
    names = _category_names(db, current.id)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["日期", "类型", "分类", "金额", "备注"])
    for t in rows:
        writer.writerow(
            [t.occurred_at, "收入" if t.type == "income" else "支出",
             names.get(t.category_id, ""), t.amount, t.note]
        )
    buf.seek(0)
    filename = f"moneymate_{month or 'all'}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
