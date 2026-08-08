"""分类接口：列表 / 新建。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_db
from ..deps import get_current_user
from ..models import Category, Transaction, User
from ..schemas import CategoryCreate, CategoryRead

router = APIRouter(prefix="/api/categories", tags=["分类"])


def _to_read(c: Category) -> CategoryRead:
    return CategoryRead(id=c.id, name=c.name, type=c.type)


@router.get("", response_model=list[CategoryRead])
def list_categories(
    type: str | None = None,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户的分类列表；可传 ?type=income|expense 过滤。"""
    query = select(Category).where(Category.user_id == current.id)
    if type:
        query = query.where(Category.type == type)
    return [_to_read(c) for c in db.exec(query.order_by(Category.id)).all()]


@router.post("", response_model=CategoryRead, status_code=201)
def create_category(
    data: CategoryCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新建分类（名称+类型组合不允许重复）。"""
    exists = db.exec(
        select(Category).where(
            Category.user_id == current.id,
            Category.name == data.name,
            Category.type == data.type,
        )
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="已存在同名同类型的分类")
    category = Category(user_id=current.id, name=data.name, type=data.type)
    db.add(category)
    db.commit()
    db.refresh(category)
    return _to_read(category)


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除分类（有流水的分类不允许删除，避免数据悬空）。"""
    category = db.get(Category, category_id)
    if not category or category.user_id != current.id:
        raise HTTPException(status_code=404, detail="分类不存在")
    if db.exec(
        select(Transaction).where(Transaction.category_id == category_id)
    ).first():
        raise HTTPException(status_code=400, detail="该分类下已有流水，不能删除")
    db.delete(category)
    db.commit()

