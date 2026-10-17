"""主动洞察：不等用户来查，先告诉他哪里不对劲。

三条规则，都刻意做成「可解释」的——每条都带上判断依据的数字，
因为记账类产品的 AI 如果只会说「你最近花得有点多」，用户不会信。

1. 预算预警：比「消耗进度」和「时间进度」，而不是简单看「已用 80%」。
   月中花了 80% 才是问题，月末花了 80% 很正常。
2. 异常消费：某笔金额超过该分类历史 P90 的两倍才提，且要求至少 5 个历史样本，
   否则新用户会被大量误报淹没。
3. 生活费见底：日均可用低于 20 元且还剩 3 天以上。

去重：用户点掉之后 24 小时内不再出现，用缓存实现（Redis 或内存兜底）。
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..cache import cache
from ..database import get_db
from ..deps import get_current_user
from ..models import Allowance, Budget, Category, Transaction, User

router = APIRouter(prefix="/api/insights", tags=["AI 洞察"])

SEEN_TTL = 24 * 3600  # 同一条洞察 24 小时内只出现一次
ANOMALY_MIN_SAMPLES = 5
ANOMALY_FACTOR = 2.0
LOW_DAILY_AVAILABLE = 20


def _p90(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))
    return ordered[idx]


def _days_in_month(month: str) -> int:
    year, mon = int(month[:4]), int(month[5:7])
    return calendar.monthrange(year, mon)[1]


def _budget_insight(user: User, db: Session, month: str, spent: Decimal) -> dict | None:
    budget = db.exec(
        select(Budget).where(Budget.user_id == user.id, Budget.month == month)
    ).first()
    if not budget or budget.amount <= 0:
        return None

    today = date.today()
    total_days = _days_in_month(month)
    is_current = month == today.strftime("%Y-%m")
    day = today.day if is_current else total_days
    time_progress = day / total_days
    spent_ratio = float(spent / budget.amount)

    # 关键判断：消耗进度明显快于时间进度才算超支风险。
    # 只看「已用 80%」会在月末误报，只看金额又不考虑已过天数。
    if spent_ratio <= time_progress + 0.1 or spent_ratio < 0.5:
        return None

    projected = float(spent) / max(time_progress, 0.01)
    return {
        "id": f"budget-{month}-{int(spent_ratio * 10)}",
        "level": "warn",
        "title": "这个月花得比时间快",
        "detail": (
            f"预算 {float(budget.amount):.0f} 元，已用 {spent_ratio:.0%}，"
            f"而时间才过 {time_progress:.0%}。按现在的速度，月底大约会花到 {projected:.0f} 元。"
        ),
        "metric": {"spent_ratio": round(spent_ratio, 3), "time_progress": round(time_progress, 3)},
    }


def _anomaly_insight(user: User, db: Session, month: str) -> dict | None:
    """找出本月明显偏离个人历史的大额单笔。"""
    today = date.today()
    since = today - timedelta(days=90)
    rows = db.exec(
        select(Transaction, Category)
        .join(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == user.id,
            Transaction.deleted_at.is_(None),
            Transaction.type == "expense",
            Transaction.occurred_at >= since,
        )
    ).all()

    history: dict[str, list[float]] = {}
    current: list[tuple[str, float, date]] = []
    for tx, cat in rows:
        value = float(tx.amount)
        if tx.occurred_at.strftime("%Y-%m") == month:
            current.append((cat.name, value, tx.occurred_at))
        else:
            history.setdefault(cat.name, []).append(value)

    flagged = []
    for name, value, occurred in current:
        samples = history.get(name, [])
        if len(samples) < ANOMALY_MIN_SAMPLES:
            continue
        threshold = _p90(samples) * ANOMALY_FACTOR
        if value > threshold:
            flagged.append((name, value, threshold, occurred))

    if not flagged:
        return None
    name, value, threshold, occurred = max(flagged, key=lambda item: item[1])
    return {
        "id": f"anomaly-{month}-{name}-{int(value)}",
        "level": "info",
        "title": "有一笔明显高于你平时的水平",
        "detail": (
            f"{occurred.isoformat()} 的「{name}」花了 {value:.0f} 元，"
            f"而你过去 90 天在这个分类的常见上限大约 {threshold / ANOMALY_FACTOR:.0f} 元。"
        ),
        "metric": {"amount": value, "threshold": round(threshold, 2)},
    }


def _allowance_insight(user: User, db: Session, month: str, spent: Decimal) -> dict | None:
    allowance = db.exec(select(Allowance).where(Allowance.user_id == user.id)).first()
    if not allowance or allowance.amount <= 0:
        return None
    today = date.today()
    total_days = _days_in_month(month)
    days_left = max(1, total_days - today.day + 1)
    remaining = float(allowance.amount - spent)
    daily = remaining / days_left
    if daily >= LOW_DAILY_AVAILABLE or days_left <= 3:
        return None
    return {
        "id": f"allowance-{month}-{int(daily)}",
        "level": "warn",
        "title": "生活费撑不到月底了",
        "detail": (
            f"还剩 {remaining:.0f} 元、{days_left} 天，"
            f"日均只能花 {daily:.1f} 元。要不要看看哪类花销可以先收一收？"
        ),
        "metric": {"remaining": round(remaining, 2), "days_left": days_left},
    }


@router.get("")
def list_insights(
    month: str = "",
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回当前值得提醒的洞察。已点掉的 24 小时内不再出现。"""
    month = month or date.today().strftime("%Y-%m")
    rows = db.exec(
        select(Transaction).where(
            Transaction.user_id == current.id,
            Transaction.deleted_at.is_(None),
            Transaction.occurred_at.startswith(month),
            Transaction.type == "expense",
        )
    ).all()
    spent = sum((t.amount for t in rows), Decimal("0"))

    candidates = [
        _budget_insight(current, db, month, spent),
        _anomaly_insight(current, db, month),
        _allowance_insight(current, db, month, spent),
    ]
    insights = []
    for item in candidates:
        if not item:
            continue
        if cache.get_json(f"insight_seen:{current.id}:{item['id']}"):
            continue
        insights.append(item)
    return {"month": month, "insights": insights}


@router.post("/{insight_id}/dismiss")
def dismiss_insight(
    insight_id: str,
    current: User = Depends(get_current_user),
):
    """用户点掉某条洞察：24 小时内不再出现同一条。"""
    cache.set_json(f"insight_seen:{current.id}:{insight_id}", {"seen": True}, ttl=SEEN_TTL)
    return {"ok": True}
