"""
MoneyMate 接口测试。

运行：.venv/bin/python tests/test_api.py

知识点：
- 每个测试用独立用户，互不依赖，任何用例失败都不影响其他用例
- TestClient 模拟 HTTP 请求，不需要启动服务器
"""

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# 测试用独立数据库，不污染开发数据
_tmp_db = os.path.join(tempfile.gettempdir(), "moneymate_test.db")
if os.path.exists(_tmp_db):
    os.remove(_tmp_db)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"
os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

# 显式建表（TestClient 不进入 with 时不会触发 lifespan）
init_db()

client = TestClient(app)

CUR_MONTH = f"{date.today():%Y-%m}"  # 例如 2026-08

_counter = 0


def _new_username() -> str:
    global _counter
    _counter += 1
    return f"user{_counter}"


def _register(username: str | None = None) -> dict:
    name = username or _new_username()
    r = client.post(
        "/api/auth/register",
        json={
            "username": name,
            "email": f"{name}@example.com",
            "password": "secret123",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _login(username: str, password: str = "secret123") -> dict:
    r = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _add_expense(headers: dict, category_id: int, amount: float, note: str = "") -> int:
    r = client.post(
        "/api/transactions",
        json={
            "category_id": category_id,
            "amount": amount,
            "type": "expense",
            "note": note,
            "occurred_at": f"{CUR_MONTH}-01",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_spa_fallback():
    """前端路由（/dashboard 等）刷新时应返回首页而不是 404（构建产物存在时）。"""
    static_dir = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "static")
    if not os.path.isdir(static_dir):
        return
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "MoneyMate" in r.text


def test_register_and_default_categories():
    user = _register()
    headers = _login(user["username"])
    r = client.get("/api/categories", headers=headers)
    assert r.status_code == 200
    names = [(c["name"], c["type"]) for c in r.json()]
    assert ("餐饮", "expense") in names
    assert ("工资", "income") in names


def test_duplicate_register():
    name = _new_username()
    _register(name)
    r = client.post(
        "/api/auth/register",
        json={"username": name, "email": f"{name}@example.com", "password": "secret123"},
    )
    assert r.status_code == 400
    assert "用户名" in r.json()["detail"]


def test_login_wrong_password():
    name = _new_username()
    _register(name)
    r = client.post("/api/auth/login", data={"username": name, "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_token():
    assert client.get("/api/auth/me").status_code == 401


def test_transaction_flow():
    user = _register()
    headers = _login(user["username"])
    cats = client.get("/api/categories", headers=headers).json()
    food = next(c for c in cats if c["name"] == "餐饮")
    salary = next(c for c in cats if c["name"] == "工资")

    # 记支出 + 收入
    _add_expense(headers, food["id"], 25.5, "午餐")
    r = client.post(
        "/api/transactions",
        json={
            "category_id": salary["id"],
            "amount": 3000,
            "type": "income",
            "note": "八月工资",
            "occurred_at": f"{CUR_MONTH}-05",
        },
        headers=headers,
    )
    assert r.status_code == 201

    # 类型与分类不匹配 → 400
    r = client.post(
        "/api/transactions",
        json={
            "category_id": food["id"],
            "amount": 10,
            "type": "income",
            "occurred_at": f"{CUR_MONTH}-02",
        },
        headers=headers,
    )
    assert r.status_code == 400

    # 本月 2 条，上个月 0 条
    assert len(client.get(f"/api/transactions?month={CUR_MONTH}", headers=headers).json()) == 2
    assert len(client.get("/api/transactions?month=2020-01", headers=headers).json()) == 0

    # 修改 + 删除
    tx_id = client.get("/api/transactions", headers=headers).json()[0]["id"]
    r = client.put(f"/api/transactions/{tx_id}", json={"note": "改备注"}, headers=headers)
    assert r.status_code == 200 and r.json()["note"] == "改备注"
    assert client.delete(f"/api/transactions/{tx_id}", headers=headers).status_code == 204


def test_budget_flow():
    user = _register()
    headers = _login(user["username"])
    food = next(
        c for c in client.get("/api/categories", headers=headers).json() if c["name"] == "餐饮"
    )
    _add_expense(headers, food["id"], 100, "先花一笔")

    r = client.put(
        f"/api/budget/{CUR_MONTH}",
        json={"month": CUR_MONTH, "amount": 2000},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["spent"] == 100  # 保存后立即返回真实支出
    r = client.get(f"/api/budget/{CUR_MONTH}", headers=headers)
    assert r.json()["amount"] == 2000
    assert r.json()["spent"] == 100


def test_category_edit_and_rules():
    user = _register()
    headers = _login(user["username"])

    # 新建分类
    r = client.post(
        "/api/categories",
        json={"name": "宠物", "type": "expense"},
        headers=headers,
    )
    assert r.status_code == 201
    cid = r.json()["id"]

    # 改名
    r = client.put(
        f"/api/categories/{cid}",
        json={"name": "宠物用品", "type": "expense"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "宠物用品"

    # 分类下有流水后：不能改类型、不能删除
    _add_expense(headers, cid, 10, "猫粮")
    r = client.put(
        f"/api/categories/{cid}",
        json={"name": "宠物用品", "type": "income"},
        headers=headers,
    )
    assert r.status_code == 400
    assert client.delete(f"/api/categories/{cid}", headers=headers).status_code == 400


def test_keyword_search():
    user = _register()
    headers = _login(user["username"])
    food = next(
        c for c in client.get("/api/categories", headers=headers).json() if c["name"] == "餐饮"
    )
    _add_expense(headers, food["id"], 10, "奶茶")
    _add_expense(headers, food["id"], 20, "外卖")

    r = client.get("/api/transactions?keyword=奶茶", headers=headers)
    assert len(r.json()) == 1
    assert r.json()[0]["note"] == "奶茶"

    r = client.get("/api/transactions?keyword=不存在", headers=headers)
    assert len(r.json()) == 0


def test_wallet_flow():
    user = _register()
    headers = _login(user["username"])

    # 注册后默认有一个「现金」钱包
    r = client.get("/api/wallets", headers=headers)
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "现金"

    # 新建微信钱包，初始余额 100
    r = client.post("/api/wallets", json={"name": "微信", "balance": 100}, headers=headers)
    assert r.status_code == 201
    wechat_id = r.json()["id"]

    # 记一笔到微信钱包
    food = next(
        c for c in client.get("/api/categories", headers=headers).json() if c["name"] == "餐饮"
    )
    r = client.post(
        "/api/transactions",
        json={
            "category_id": food["id"],
            "wallet_id": wechat_id,
            "amount": 20,
            "type": "expense",
            "note": "奶茶",
            "occurred_at": f"{CUR_MONTH}-01",
        },
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["wallet_name"] == "微信"

    # 微信钱包实时余额 = 100 - 20 = 80
    r = client.get("/api/wallets", headers=headers)
    wechat = next(w for w in r.json() if w["id"] == wechat_id)
    assert wechat["balance"] == 80
    assert wechat["transaction_count"] == 1

    # 有流水的钱包不能删除
    assert client.delete(f"/api/wallets/{wechat_id}", headers=headers).status_code == 400


def test_monthly_summary():
    user = _register()
    headers = _login(user["username"])
    cats = client.get("/api/categories", headers=headers).json()
    food = next(c for c in cats if c["name"] == "餐饮")
    salary = next(c for c in cats if c["name"] == "工资")

    _add_expense(headers, food["id"], 30, "奶茶")
    _add_expense(headers, food["id"], 50, "外卖")
    client.post(
        "/api/transactions",
        json={
            "category_id": salary["id"],
            "amount": 3000,
            "type": "income",
            "note": "八月工资",
            "occurred_at": f"{CUR_MONTH}-01",
        },
        headers=headers,
    )

    r = client.get(f"/api/stats/monthly-summary?month={CUR_MONTH}", headers=headers)
    assert r.status_code == 200
    text = r.json()["text"]
    assert "月度总结" in text
    assert "3000" in text
    assert "奶茶" in text
    assert "外卖" in text


def test_annual_report():
    user = _register()
    headers = _login(user["username"])
    cats = client.get("/api/categories", headers=headers).json()
    food = next(c for c in cats if c["name"] == "餐饮")
    salary = next(c for c in cats if c["name"] == "工资")

    # 同年 2 个月的数据 + 一笔奶茶
    for day in ("01", "15"):
        client.post(
            "/api/transactions",
            json={
                "category_id": food["id"],
                "amount": 30,
                "type": "expense",
                "note": "奶茶",
                "occurred_at": f"2026-01-{day}",
            },
            headers=headers,
        )
    client.post(
        "/api/transactions",
        json={
            "category_id": salary["id"],
            "amount": 5000,
            "type": "income",
            "note": "工资",
            "occurred_at": "2026-02-01",
        },
        headers=headers,
    )

    r = client.get("/api/stats/annual-report?year=2026", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["year"] == 2026
    assert data["total_expense"] == 60
    assert data["total_income"] == 5000
    assert len(data["monthly"]) == 12
    assert data["monthly"][0]["expense"] == 60  # 1 月
    assert data["monthly"][1]["income"] == 5000  # 2 月
    assert any("奶茶" in f for f in data["fun_facts"])
    assert data["summary"]


def test_stats():
    user = _register()
    headers = _login(user["username"])
    cats = client.get("/api/categories", headers=headers).json()
    food = next(c for c in cats if c["name"] == "餐饮")
    salary = next(c for c in cats if c["name"] == "工资")
    _add_expense(headers, food["id"], 25.5, "午餐")
    client.post(
        "/api/transactions",
        json={
            "category_id": salary["id"],
            "amount": 3000,
            "type": "income",
            "occurred_at": f"{CUR_MONTH}-05",
        },
        headers=headers,
    )

    r = client.get(f"/api/stats/summary?month={CUR_MONTH}", headers=headers)
    data = r.json()
    assert data["total_income"] == 3000
    assert data["total_expense"] == 25.5
    assert data["expense_by_category"][0]["category_name"] == "餐饮"

    r = client.get("/api/stats/trend?months=3", headers=headers)
    points = r.json()["points"]
    assert len(points) == 3
    assert points[-1]["month"] == CUR_MONTH
    assert points[-1]["income"] == 3000


def test_export_csv():
    user = _register()
    headers = _login(user["username"])
    food = next(
        c for c in client.get("/api/categories", headers=headers).json() if c["name"] == "餐饮"
    )
    _add_expense(headers, food["id"], 66, "导出测试")

    r = client.get(f"/api/transactions/export?month={CUR_MONTH}", headers=headers)
    assert r.status_code == 200
    assert "日期,类型,分类,金额,备注" in r.text
    assert "66" in r.text


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except Exception as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
    total = len([n for n in globals() if n.startswith("test_")])
    print(f"\n结果：{total - failures} 通过，{failures} 失败")
    sys.exit(1 if failures else 0)
