"""AI 对话入口：一个对话框里完成记账 / 查询 / 改预算 / 咨询。

和原来的三个「AI 按钮」的区别：

- 原来：一句话记账、智能分类、月度总结各是一个独立接口，互不知道对方存在，
  用户得先想「这件事该点哪个按钮」。
- 现在：模型自己判断该调哪个工具，用户只需要把话说清楚。

一个刻意的边界：**写操作只生成草稿，不直接落库**。
`record_transaction` 和 `set_budget` 返回的是待确认的动作，
真正写入仍走原来的 POST /transactions 与 PUT /budget。
记账是有副作用的操作，AI 判断错了让用户点一下的成本，
远低于记错一笔再让他去改。
"""

import calendar
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import llm
from ..constants import CATEGORY_HINTS, FALLBACK_EXPENSE_CATEGORY, FALLBACK_INCOME_CATEGORY
from ..database import get_db
from ..deps import get_current_user
from ..models import Allowance, Budget, Category, Transaction, User, Wallet
from ..rate_limit import rate_limit

router = APIRouter(prefix="/api/chat", tags=["AI 对话"])

MAX_ROUNDS = 3

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "record_transaction",
            "description": "用户要记一笔收支时调用。只生成待确认的草稿，不直接写入数据库。",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["expense", "income"]},
                    "amount": {"type": "number", "description": "金额（元），必须来自用户原话"},
                    "category": {"type": "string", "description": "分类名，必须从系统给出的分类里选"},
                    "note": {"type": "string", "description": "简短备注，10 字以内"},
                    "date": {"type": "string", "description": "日期 YYYY-MM-DD，默认今天"},
                    "wallet": {"type": "string", "description": "钱包名，可省略"},
                },
                "required": ["type", "amount", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_spending",
            "description": "查询某个月的花销，可按分类过滤。用户问「这个月外卖花了多少」时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "月份 YYYY-MM，默认当前月"},
                    "category": {"type": "string", "description": "分类名，可选"},
                    "type": {"type": "string", "enum": ["expense", "income"], "description": "默认 expense"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_budget",
            "description": "用户要设置或修改某个月的预算时调用。只生成待确认的草稿。",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "月份 YYYY-MM，默认当前月"},
                    "amount": {"type": "number", "description": "预算金额（元）"},
                },
                "required": ["amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "查询本月生活费、预算执行情况、剩余可用天数。用户问「我还剩多少钱」时调用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

SYSTEM_TEMPLATE = """你是大学生的记账助手，语气自然，像一个熟悉的朋友。

你能做四件事：记账、查花销、改预算、回答消费相关的问题。
需要数据时必须调用工具，不要凭空猜测数字。

规则：
1. 金额只能来自用户原话。用户没说金额就问清楚，绝对不要自己编一个数。
2. 分类必须从下面列表里选，按冒号后的口径判断：
{categories}
3. 钱包可选：{wallets}
4. 记账和改预算只是生成草稿，用户确认后才真正生效，回复时说明「确认后才会记账」。
5. 回答简短，不要用列表堆砌，不要提「作为一个 AI」。

今天是 {today}。"""


def _category_block(categories: list[Category]) -> str:
    lines = []
    for c in categories:
        if c.type != "expense":
            continue
        hint = CATEGORY_HINTS.get(c.name)
        lines.append(f"- {c.name}：{hint}" if hint else f"- {c.name}")
    return "\n".join(lines) or "（无）"


def _money(value) -> Decimal:
    try:
        return round(Decimal(str(value)), 2)
    except (TypeError, ValueError, InvalidOperation):
        return Decimal("0")


def _parse_month(raw: str | None) -> str:
    if raw and len(str(raw)) == 7 and str(raw)[4] == "-":
        return str(raw)
    return date.today().strftime("%Y-%m")


# ---------------- 工具实现 ----------------

def _tool_record_transaction(args: dict, current: User, db: Session) -> dict:
    """生成记账草稿。校验全部在这里做完，前端拿到的就是可提交的数据。"""
    type_ = args.get("type") if args.get("type") in ("expense", "income") else "expense"
    amount = _money(args.get("amount"))
    if amount <= 0:
        return {"ok": False, "error": "金额必须大于 0，请问用户这笔花了多少"}

    categories = db.exec(select(Category).where(Category.user_id == current.id)).all()
    name = str(args.get("category", "")).strip()
    cat = next((c for c in categories if c.name == name and c.type == type_), None)
    if cat is None:
        wanted = FALLBACK_EXPENSE_CATEGORY if type_ == "expense" else FALLBACK_INCOME_CATEGORY
        cat = next((c for c in categories if c.name == wanted and c.type == type_), None) or categories[0]

    wallets = db.exec(select(Wallet).where(Wallet.user_id == current.id)).all()
    wallet_name = str(args.get("wallet", "")).strip()
    wallet = next((w for w in wallets if w.name == wallet_name), None) or (wallets[0] if wallets else None)

    try:
        occurred_at = date.fromisoformat(str(args.get("date") or ""))
        if occurred_at > date.today():
            occurred_at = date.today()
    except ValueError:
        occurred_at = date.today()

    draft = {
        "category_id": cat.id,
        "category": cat.name,
        "wallet_id": wallet.id if wallet else None,
        "wallet": wallet.name if wallet else None,
        "amount": float(amount),
        "type": type_,
        "note": str(args.get("note", "")).strip()[:20] or cat.name,
        "occurred_at": occurred_at.isoformat(),
    }
    return {
        "ok": True,
        "action": {"kind": "transaction", "draft": draft},
        "hint": "已生成记账草稿，等用户点确认后才写入",
    }


def _tool_query_spending(args: dict, current: User, db: Session) -> dict:
    month = _parse_month(args.get("month"))
    type_ = args.get("type") if args.get("type") in ("expense", "income") else "expense"
    rows = db.exec(
        select(Transaction, Category)
        .join(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == current.id,
            Transaction.occurred_at.startswith(month),
            Transaction.type == type_,
        )
    ).all()
    by_cat: dict[str, dict] = {}
    total = Decimal("0")
    for tx, cat in rows:
        item = by_cat.setdefault(cat.name, {"amount": Decimal("0"), "count": 0})
        item["amount"] += tx.amount
        item["count"] += 1
        total += tx.amount

    wanted = str(args.get("category", "")).strip()
    if wanted:
        picked = by_cat.get(wanted)
        if picked is None:
            return {"ok": True, "month": month, "category": wanted, "amount": 0, "count": 0}
        return {
            "ok": True,
            "month": month,
            "category": wanted,
            "amount": float(picked["amount"]),
            "count": picked["count"],
        }

    top = sorted(by_cat.items(), key=lambda kv: kv[1]["amount"], reverse=True)[:5]
    return {
        "ok": True,
        "month": month,
        "type": type_,
        "total": float(total),
        "count": len(rows),
        "by_category": [
            {"name": name, "amount": float(v["amount"]), "count": v["count"]} for name, v in top
        ],
    }


def _tool_set_budget(args: dict, current: User, db: Session) -> dict:
    amount = _money(args.get("amount"))
    if amount <= 0:
        return {"ok": False, "error": "预算金额必须大于 0"}
    month = _parse_month(args.get("month"))
    existing = db.exec(
        select(Budget).where(Budget.user_id == current.id, Budget.month == month)
    ).first()
    return {
        "ok": True,
        "action": {
            "kind": "budget",
            "draft": {"month": month, "amount": float(amount), "previous": float(existing.amount) if existing else None},
        },
        "hint": "已生成预算草稿，等用户确认后才生效",
    }


def _tool_get_status(args: dict, current: User, db: Session) -> dict:
    month = date.today().strftime("%Y-%m")
    allowance = db.exec(select(Allowance).where(Allowance.user_id == current.id)).first()
    budget = db.exec(
        select(Budget).where(Budget.user_id == current.id, Budget.month == month)
    ).first()
    rows = db.exec(
        select(Transaction).where(
            Transaction.user_id == current.id,
            Transaction.occurred_at.startswith(month),
            Transaction.type == "expense",
        )
    ).all()
    spent = sum((t.amount for t in rows), Decimal("0"))
    days_in_month = calendar.monthrange(date.today().year, date.today().month)[1]
    days_left = days_in_month - date.today().day + 1
    return {
        "ok": True,
        "month": month,
        "allowance": float(allowance.amount) if allowance else None,
        "budget": float(budget.amount) if budget else None,
        "spent": float(spent),
        "days_left": days_left,
        "daily_available": round(float(allowance.amount - spent) / days_left, 2)
        if allowance and days_left > 0
        else None,
    }


_TOOL_IMPL = {
    "record_transaction": _tool_record_transaction,
    "query_spending": _tool_query_spending,
    "set_budget": _tool_set_budget,
    "get_status": _tool_get_status,
}


def run_chat(text: str, current: User, db: Session) -> dict:
    """跑完一轮工具调用循环，返回回复 + 待确认动作 + 轨迹。

    最多 3 轮：记账场景几乎不需要更深的多步规划，
    轮数上限既是成本控制，也避免模型在工具之间来回打转。
    """
    categories = db.exec(select(Category).where(Category.user_id == current.id)).all()
    wallets = db.exec(select(Wallet).where(Wallet.user_id == current.id)).all()
    system = SYSTEM_TEMPLATE.format(
        categories=_category_block(categories),
        wallets="、".join(w.name for w in wallets) or "（无）",
        today=date.today().isoformat(),
    )

    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
    actions: list[dict] = []
    trace: list[dict] = []

    for _ in range(MAX_ROUNDS):
        result = llm.chat_tools(messages, TOOLS)
        calls = result["tool_calls"]
        if not calls:
            return {
                "reply": result["content"] or "抱歉，我没太理解，可以换个说法吗？",
                "actions": actions,
                "trace": trace,
            }

        messages.append(
            {
                "role": "assistant",
                "content": result["content"],
                "tool_calls": [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c["arguments"]},
                    }
                    for c in calls
                ],
            }
        )
        for call in calls:
            impl = _TOOL_IMPL.get(call["name"])
            try:
                args = json.loads(call["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            if impl is None:
                payload = {"ok": False, "error": f"未知工具 {call['name']}"}
            else:
                try:
                    payload = impl(args, current, db)
                except Exception as exc:  # noqa: BLE001
                    payload = {"ok": False, "error": f"工具执行失败：{exc}"}
            if payload.get("action"):
                actions.append(payload["action"])
            trace.append({"tool": call["name"], "args": args, "result": payload})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            )

    return {
        "reply": "这个请求有点复杂，我先说到这儿。你可以拆成一句一句问我，比如先记账再问花销。",
        "actions": actions,
        "trace": trace,
    }


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)


@router.post("")
def ai_chat(
    data: ChatIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 对话入口。写操作只返回草稿，需前端二次确认。"""
    text = data.message.strip()
    if not text:
        raise HTTPException(status_code=422, detail="请输入内容")
    rate_limit(current.id, "ai_chat", limit=20)
    try:
        return run_chat(text, current, db)
    except llm.LLMError as e:
        raise HTTPException(status_code=503, detail=f"AI 服务暂不可用：{e}")
