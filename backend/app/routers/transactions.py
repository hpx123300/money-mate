"""流水接口：增删改查 + 筛选 + CSV 导出。"""

import csv
import io
import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlmodel import Session, func, select

from ..cache import cache
from ..database import get_db
from ..deps import get_current_user
from ..models import Category, Transaction, User, Wallet
from ..schemas import (
    ImportResult,
    TransactionCreate,
    TransactionPage,
    TransactionRead,
    TransactionUpdate,
)

router = APIRouter(prefix="/api/transactions", tags=["流水"])


def _to_read(
    t: Transaction,
    categories: dict[int, str],
    wallets: dict[int, str],
) -> TransactionRead:
    return TransactionRead(
        id=t.id,
        category_id=t.category_id,
        category_name=categories.get(t.category_id, ""),
        wallet_id=t.wallet_id,
        wallet_name=wallets.get(t.wallet_id, "") if t.wallet_id else "",
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


def _wallet_names(db: Session, user_id: int) -> dict[int, str]:
    return {
        w.id: w.name
        for w in db.exec(select(Wallet).where(Wallet.user_id == user_id)).all()
    }


@router.get("", response_model=TransactionPage)
def list_transactions(
    month: str | None = None,      # 2026-08
    type: str | None = None,       # income / expense
    category_id: int | None = None,
    wallet_id: int | None = None,
    keyword: str | None = None,    # 备注关键词搜索
    page: int = 1,
    page_size: int = 20,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    流水列表，支持筛选 + 分页。
    分页是生产接口的标配：数据量大时一次只取一页，前端翻页再取。
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    conditions = [Transaction.user_id == current.id]
    if month:
        conditions.append(Transaction.occurred_at.startswith(month))
    if type:
        conditions.append(Transaction.type == type)
    if category_id:
        conditions.append(Transaction.category_id == category_id)
    if wallet_id:
        conditions.append(Transaction.wallet_id == wallet_id)
    if keyword:
        conditions.append(Transaction.note.contains(keyword))

    total = db.exec(select(func.count(Transaction.id)).where(*conditions)).one()
    rows = db.exec(
        select(Transaction)
        .where(*conditions)
        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    names = _category_names(db, current.id)
    wallets = _wallet_names(db, current.id)
    return TransactionPage(
        total=total or 0,
        page=page,
        page_size=page_size,
        items=[_to_read(t, names, wallets) for t in rows],
    )


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
    if data.wallet_id:
        wallet = db.get(Wallet, data.wallet_id)
        if not wallet or wallet.user_id != current.id:
            raise HTTPException(status_code=400, detail="钱包不存在")
    t = Transaction(
        user_id=current.id,
        category_id=data.category_id,
        wallet_id=data.wallet_id,
        amount=data.amount,
        type=data.type,
        note=data.note,
        occurred_at=data.occurred_at,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    # 数据变了，清掉该用户的统计缓存
    cache.delete_prefix(f"stats:{current.id}:")
    return _to_read(t, _category_names(db, current.id), _wallet_names(db, current.id))


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
    cache.delete_prefix(f"stats:{current.id}:")
    return _to_read(t, _category_names(db, current.id), _wallet_names(db, current.id))


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
    cache.delete_prefix(f"stats:{current.id}:")


# ============================================================
# 账单导入（支付宝/微信 CSV）
# ============================================================

# 常见列名别名：帮助识别不同来源的账单格式
_HEADER_ALIASES = {
    "date": ["交易时间", "交易日期", "时间", "日期"],
    "type": ["收/支", "收支", "收入/支出", "类型"],
    "amount": ["金额(元)", "金额", "发生额"],
    "note": ["商品说明", "商品", "备注", "说明", "交易对方"],
    "category": ["交易分类", "分类"],
}


def _decode_csv(raw: bytes) -> str:
    """支付宝导出的 CSV 可能是 GBK/GB18030 编码，依次尝试解码。"""
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _parse_date(value: str) -> date | None:
    m = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", value)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _parse_amount(value: str) -> float | None:
    cleaned = re.sub(r"[^\d.\-]", "", value)
    if not cleaned or cleaned in ("-", "."):
        return None
    try:
        return abs(float(cleaned))
    except ValueError:
        return None


def _parse_type(value: str, amount: float | None) -> str | None:
    v = value.strip()
    if v in ("收", "收入", "income", "+"):
        return "income"
    if v in ("支", "支出", "expense", "-"):
        return "expense"
    # 有些导出金额为负数表示支出
    if re.search(r"-\d", value):
        return "expense"
    if amount is not None:
        return "expense"  # 识别不了时按支出处理，避免误判为收入
    return None


def _parse_csv_rows(text: str) -> tuple[list[dict], list[str]]:
    """把 CSV 文本解析成 [{date, type, amount, note, category}]，识别表头列名。"""
    reader = csv.reader(io.StringIO(text))
    all_rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not all_rows:
        return [], ["文件为空"]

    # 找表头行：包含「金额」或「日期」关键词的那一行
    header_idx = None
    for i, row in enumerate(all_rows[:20]):
        joined = ",".join(row)
        if "金额" in joined or "日期" in joined:
            header_idx = i
            break
    if header_idx is None:
        # 没有表头：按我们的模板顺序处理（日期,类型,分类,金额,备注）
        header = ["日期", "类型", "分类", "金额", "备注"]
        start = 0
    else:
        header = all_rows[header_idx]
        start = header_idx + 1

    col_map: dict[str, int] = {}
    for key, aliases in _HEADER_ALIASES.items():
        # 按别名优先级匹配（而不是按列顺序），避免「交易对方」抢先占用备注列
        for alias in aliases:
            for idx, cell in enumerate(header):
                cell_clean = cell.strip().lower()
                if cell_clean == alias.lower() or alias.lower() in cell_clean:
                    col_map[key] = idx
                    break
            if key in col_map:
                break

    # 我们的模板列名统一映射
    for key, name in (("date", "日期"), ("type", "类型"), ("amount", "金额"), ("note", "备注"), ("category", "分类")):
        if key not in col_map and name in header:
            col_map[key] = header.index(name)

    rows: list[dict] = []
    errors: list[str] = []
    for row_num, row in enumerate(all_rows[start:], start=start + 1):
        def cell(key: str) -> str:
            idx = col_map.get(key)
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        d = _parse_date(cell("date"))
        amount = _parse_amount(cell("amount"))
        t = _parse_type(cell("type"), amount)
        if d is None or amount is None or t is None:
            errors.append(f"第 {row_num} 行无法解析（日期/金额/类型缺失或格式错误）")
            continue
        rows.append(
            {
                "occurred_at": d,
                "type": t,
                "amount": amount,
                "note": cell("note")[:200] or "",
                "category_name": cell("category")[:20] or "",
            }
        )
    return rows, errors


@router.post("/import", response_model=ImportResult)
async def import_transactions(
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    导入账单 CSV：支持支付宝/微信导出的文件（自动识别列名），
    也支持下载模板格式。重复流水自动跳过，分类自动匹配。
    """
    raw = await file.read()
    text = _decode_csv(raw)
    rows, errors = _parse_csv_rows(text)

    # 用户分类映射：名称 -> Category
    categories = {
        c.name: c
        for c in db.exec(select(Category).where(Category.user_id == current.id)).all()
    }

    # 已有流水集合，用于去重（同用户 + 同日期 + 同金额 + 同备注）
    existing = {
        (t.occurred_at, t.amount, t.note)
        for t in db.exec(select(Transaction).where(Transaction.user_id == current.id)).all()
    }

    imported = 0
    skipped = 0
    for row in rows:
        key = (row["occurred_at"], row["amount"], row["note"])
        if key in existing:
            skipped += 1
            continue

        # 分类匹配：先精确、再包含、最后用默认「其他」
        category = None
        cname = row["category_name"]
        if cname:
            category = categories.get(cname)
            if category is None:
                for name, cat in categories.items():
                    if cname in name or name in cname:
                        category = cat
                        break
        if category is None:
            default_name = "其他支出" if row["type"] == "expense" else "其他收入"
            category = categories.get(default_name)
            if category is None:
                category = Category(
                    user_id=current.id, name=default_name, type=row["type"]
                )
                db.add(category)
                db.flush()
                categories[default_name] = category

        db.add(
            Transaction(
                user_id=current.id,
                category_id=category.id,
                amount=row["amount"],
                type=row["type"],
                note=row["note"],
                occurred_at=row["occurred_at"],
            )
        )
        existing.add(key)
        imported += 1

    db.commit()
    cache.delete_prefix(f"stats:{current.id}:")
    return ImportResult(
        total_rows=len(rows),
        imported=imported,
        skipped_duplicates=skipped,
        failed=len(errors),
        errors=errors[:20],
    )


@router.get("/import-template")
def import_template():
    """下载导入模板 CSV。"""
    content = (
        "日期,类型,分类,金额,备注\n"
        "2026-08-01,支出,餐饮,25.5,午餐\n"
        "2026-08-02,收入,工资,3000,八月工资\n"
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="moneymate_template.csv"'},
    )


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
