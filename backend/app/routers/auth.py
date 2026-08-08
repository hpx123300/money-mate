"""认证接口：注册 / 登录 / 当前用户。"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from ..database import get_db
from ..deps import get_current_user
from ..models import Category, User, Wallet
from ..schemas import Token, UserCreate, UserRead
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 新用户自动创建的默认分类
DEFAULT_CATEGORIES = [
    ("餐饮", "expense"),
    ("外卖", "expense"),
    ("购物", "expense"),
    ("宿舍水电", "expense"),
    ("交通", "expense"),
    ("娱乐", "expense"),
    ("学习", "expense"),
    ("医疗", "expense"),
    ("其他支出", "expense"),
    ("生活费", "income"),
    ("兼职", "income"),
    ("奖学金", "income"),
    ("其他收入", "income"),
]


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """注册：校验用户名/邮箱唯一，密码哈希后入库，并创建默认分类。"""
    if db.exec(select(User).where(User.username == data.username)).first():
        raise HTTPException(status_code=400, detail="用户名已被使用")
    if db.exec(select(User).where(User.email == data.email)).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.flush()  # 拿到自增 id

    # 注册即送一套默认分类，省去新手手动配置
    for name, ctype in DEFAULT_CATEGORIES:
        db.add(Category(user_id=user.id, name=name, type=ctype))
    # 默认一个「现金」钱包，之后用户自己加微信/支付宝等
    db.add(Wallet(user_id=user.id, name="现金", balance=0))

    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """登录：OAuth2 密码模式，成功返回 JWT。"""
    user = db.exec(select(User).where(User.username == form.username)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
def me(current: User = Depends(get_current_user)):
    """返回当前登录用户信息（前端用来判断是否已登录）。"""
    return current
