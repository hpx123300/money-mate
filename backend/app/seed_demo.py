"""演示数据初始化：给线上演示站造一个带真实感数据的演示账号。

触发条件（满足其一即可，且库里还没有演示账号时才会生成）：
- 环境变量 SEED_DEMO_DATA=true
- APP_ENV=production

演示账号：demo / demo123456
生成内容：微信/支付宝/现金三个钱包、近 4 个月收支流水、
生活费设置（每月 2000，1 号到账）、当月预算。
"""

import random
from datetime import date, timedelta

from sqlmodel import Session, select

from .config import settings
from .database import engine, init_db
from .models import Allowance, Budget, Category, Transaction, User, Wallet
from .routers.auth import DEFAULT_CATEGORIES
from .security import hash_password

DEMO_USERNAME = "demo"
DEMO_EMAIL = "demo@demo.com"
DEMO_PASSWORD = "demo123456"


def _month_first(back: int) -> date:
    """返回 back 个月前那个月的 1 号（back=0 是当月）。"""
    today = date.today()
    year, month = today.year, today.month
    for _ in range(back):
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return date(year, month, 1)


def _generate_transactions(
    user_id: int,
    wallets: dict,
    cats: dict,
) -> list[Transaction]:
    """用固定随机种子生成近 4 个月的收支流水，保证每次演示数据都一致。"""
    rng = random.Random(42)
    today = date.today()
    rows: list[Transaction] = []

    for back in range(3, -1, -1):
        first = _month_first(back)
        if back == 0:
            last = today
        else:
            nxt = _month_first(back - 1)
            last = nxt - timedelta(days=1)

        def add(day: int, ctype: str, cat: str, amount: float, wallet: str, note: str):
            d = date(first.year, first.month, day)
            if d > last:
                return
            rows.append(
                Transaction(
                    user_id=user_id,
                    category_id=cats[cat].id,
                    wallet_id=wallets[wallet].id,
                    amount=round(amount, 2),
                    type=cats[cat].type,
                    note=note,
                    occurred_at=d,
                )
            )

        # ---- 收入 ----
        add(1, "income", "生活费", 2000, "微信", "爸妈转的生活费")
        add(10, "income", "兼职", 480, "支付宝", "奶茶店周末兼职")
        if back == 3:
            add(15, "income", "奖学金", 2000, "支付宝", "上学期奖学金到账")

        # ---- 支出：食堂 / 外卖 / 奶茶 / 交通 ----
        for _ in range(rng.randint(10, 14)):
            add(
                rng.randint(2, 28), "expense", "餐饮",
                rng.uniform(10, 20), rng.choice(["微信", "支付宝"]),
                rng.choice(["食堂午餐", "食堂早餐+豆浆", "食堂晚饭", "食堂麻辣香锅"]),
            )
        for _ in range(rng.randint(4, 6)):
            add(
                rng.randint(2, 28), "expense", "外卖",
                rng.uniform(18, 38), "支付宝",
                rng.choice(["麻辣烫", "黄焖鸡米饭", "螺蛳粉", "炸鸡汉堡"]),
            )
        for _ in range(rng.randint(3, 5)):
            add(
                rng.randint(2, 28), "expense", "餐饮",
                rng.uniform(12, 20), "微信",
                rng.choice(["奶茶", "果茶", "咖啡"]),
            )
        for _ in range(rng.randint(8, 12)):
            add(
                rng.randint(2, 28), "expense", "交通",
                rng.uniform(4, 9), rng.choice(["微信", "支付宝"]),
                "地铁出行",
            )

        # ---- 固定月支出 ----
        add(rng.randint(20, 27), "expense", "宿舍水电", rng.uniform(60, 100), "现金", "宿舍水电费")
        if rng.random() < 0.85:
            add(
                rng.randint(2, 26), "expense", "学习",
                rng.uniform(30, 150), "支付宝",
                rng.choice(["打印复习资料", "买教材", "考试报名费"]),
            )
        if rng.random() < 0.8:
            add(
                rng.randint(2, 27), "expense", "购物",
                rng.uniform(80, 300), "支付宝",
                rng.choice(["换季衣服", "日用品囤货", "宿舍小电器"]),
            )
        if rng.random() < 0.7:
            add(
                rng.randint(2, 27), "expense", "娱乐",
                rng.uniform(40, 100), "微信",
                rng.choice(["看电影", "和同学唱K", "密室逃脱"]),
            )
        for _ in range(rng.randint(1, 2)):
            add(
                rng.randint(2, 27), "expense", "其他支出",
                rng.uniform(30, 90), rng.choice(["微信", "支付宝"]),
                rng.choice(["水果零食", "日用品", "宿舍团购"]),
            )
    return rows


def seed_demo(db: Session) -> bool:
    """创建演示账号和数据；已存在则跳过。返回是否真的创建了。"""
    if db.exec(select(User).where(User.email == DEMO_EMAIL)).first():
        return False

    user = User(
        username=DEMO_USERNAME,
        email=DEMO_EMAIL,
        hashed_password=hash_password(DEMO_PASSWORD),
    )
    db.add(user)
    db.flush()

    for name, ctype in DEFAULT_CATEGORIES:
        db.add(Category(user_id=user.id, name=name, type=ctype))

    wallets = {
        name: Wallet(user_id=user.id, name=name, balance=0)
        for name in ["微信", "支付宝", "现金"]
    }
    for wallet in wallets.values():
        db.add(wallet)
    db.flush()

    cats = {
        c.name: c
        for c in db.exec(select(Category).where(Category.user_id == user.id)).all()
    }
    for row in _generate_transactions(user.id, wallets, cats):
        db.add(row)

    db.add(Allowance(user_id=user.id, amount=2000, day_of_month=1))
    db.add(Budget(user_id=user.id, month=date.today().strftime("%Y-%m"), amount=1800))
    db.commit()
    return True


def maybe_seed_demo() -> bool:
    """启动时调用：满足开关条件且无演示账号时初始化演示数据。"""
    if not (settings.seed_demo_data or settings.app_env == "production"):
        return False
    with Session(engine) as session:
        return seed_demo(session)


if __name__ == "__main__":
    init_db()
    with Session(engine) as session:
        created = seed_demo(session)
    print("已创建演示数据" if created else "演示账号已存在，跳过")
