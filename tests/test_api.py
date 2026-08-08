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
    r = client.get(f"/api/budget/{CUR_MONTH}", headers=headers)
    assert r.json()["amount"] == 2000
    assert r.json()["spent"] == 100


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
