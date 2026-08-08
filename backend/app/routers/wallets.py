"""钱包接口：多钱包管理（微信/支付宝/现金…）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from ..database import get_db
from ..deps import get_current_user
from ..models import Transaction, User, Wallet
from ..schemas import WalletCreate, WalletRead

router = APIRouter(prefix="/api/wallets", tags=["钱包"])


def _read_wallet(db: Session, wallet: Wallet) -> WalletRead:
    """实时余额 = 初始余额 + 收入 - 支出"""
    income = db.exec(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.wallet_id == wallet.id,
            Transaction.type == "income",
        )
    ).one()
    expense = db.exec(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.wallet_id == wallet.id,
            Transaction.type == "expense",
        )
    ).one()
    count = db.exec(
        select(func.count(Transaction.id)).where(Transaction.wallet_id == wallet.id)
    ).one()
    return WalletRead(
        id=wallet.id,
        name=wallet.name,
        balance=round(wallet.balance + (income or 0) - (expense or 0), 2),
        transaction_count=count or 0,
    )


@router.get("", response_model=list[WalletRead])
def list_wallets(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallets = db.exec(
        select(Wallet).where(Wallet.user_id == current.id).order_by(Wallet.id)
    ).all()
    return [_read_wallet(db, w) for w in wallets]


@router.post("", response_model=WalletRead, status_code=201)
def create_wallet(
    data: WalletCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exists = db.exec(
        select(Wallet).where(
            Wallet.user_id == current.id, Wallet.name == data.name
        )
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="已存在同名钱包")
    wallet = Wallet(user_id=current.id, name=data.name, balance=data.balance)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return _read_wallet(db, wallet)


@router.put("/{wallet_id}", response_model=WalletRead)
def update_wallet(
    wallet_id: int,
    data: WalletCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = db.get(Wallet, wallet_id)
    if not wallet or wallet.user_id != current.id:
        raise HTTPException(status_code=404, detail="钱包不存在")
    wallet.name = data.name
    wallet.balance = data.balance
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return _read_wallet(db, wallet)


@router.delete("/{wallet_id}", status_code=204)
def delete_wallet(
    wallet_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = db.get(Wallet, wallet_id)
    if not wallet or wallet.user_id != current.id:
        raise HTTPException(status_code=404, detail="钱包不存在")
    has_tx = db.exec(
        select(Transaction).where(Transaction.wallet_id == wallet_id)
    ).first()
    if has_tx:
        raise HTTPException(status_code=400, detail="该钱包下已有流水，不能删除")
    db.delete(wallet)
    db.commit()
