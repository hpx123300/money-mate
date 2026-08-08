"""
线上冒烟测试：对着运行中的服务（本地 Docker 或线上部署）跑一遍核心流程。

用法：
    .venv/bin/python tests/test_live.py
    MONEYMATE_URL=https://你的线上地址 .venv/bin/python tests/test_live.py
"""

import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
import uuid

BASE = os.getenv("MONEYMATE_URL", "http://127.0.0.1:8000")

failures = 0
total = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global failures, total
    total += 1
    if cond:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail}")


def request(method: str, path: str, body=None, headers=None, files=None):
    # 路径/查询参数里可能含中文（如 keyword=奶茶），需要 URL 编码
    url = urllib.parse.quote(BASE + path, safe="/:?=&%")
    data = None
    req_headers = dict(headers or {})
    if files:
        boundary = "----moneymate" + uuid.uuid4().hex
        parts = []
        for field, (filename, content, ctype) in files.items():
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n"
            )
            parts.append(content.decode("utf-8", "ignore"))
            parts.append("\r\n")
        parts.append(f"--{boundary}--\r\n")
        data = "".join(parts).encode("utf-8")
        req_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", "ignore")
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "ignore")


def main():
    # ---------- 基础 ----------
    code, raw = request("GET", "/api/health")
    check("健康检查", code == 200 and '"status":"ok"' in raw, f"{code} {raw}")

    for path in ("/dashboard", "/transactions", "/budget", "/report"):
        code, raw = request("GET", path)
        check(f"前端路由 {path}", code == 200 and "大学生记账助手" in raw, f"{code}")

    # ---------- 账号 ----------
    name = "smoke" + uuid.uuid4().hex[:6]
    code, raw = request(
        "POST", "/api/auth/register",
        {"username": name, "email": f"{name}@test.com", "password": "test123"},
    )
    check("注册", code == 201, f"{code} {raw}")

    code, raw = request(
        "POST", "/api/auth/register",
        {"username": name, "email": f"{name}@test.com", "password": "test123"},
    )
    check("重复注册被拒绝", code == 400, f"{code} {raw}")

    req = urllib.request.Request(
        BASE + "/api/auth/login",
        data=f"username={name}&password=test123".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        token = json.loads(resp.read())["access_token"]
    check("登录", bool(token), "未拿到令牌")
    auth = {"Authorization": f"Bearer {token}"}

    req = urllib.request.Request(
        BASE + "/api/auth/login",
        data=f"username={name}&password=wrong".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        check("错误密码被拒绝", False, "竟然登录成功了")
    except urllib.error.HTTPError as exc:
        check("错误密码被拒绝", exc.code == 401, str(exc.code))

    code, raw = request("GET", "/api/auth/me", headers=auth)
    check("当前用户", code == 200 and name in raw, f"{code} {raw}")

    # ---------- 分类 ----------
    code, raw = request("GET", "/api/categories", headers=auth)
    cats = json.loads(raw)
    check("学生分类", code == 200 and any(c["name"] == "宿舍水电" for c in cats), raw[:100])
    expense_cat = next(c for c in cats if c["name"] == "餐饮")
    income_cat = next(c for c in cats if c["name"] == "生活费")

    code, raw = request(
        "POST", "/api/categories", {"name": "社团", "type": "expense"}, headers=auth
    )
    check("新建分类", code == 201, f"{code} {raw}")
    new_cat = json.loads(raw)["id"]

    # ---------- 钱包 ----------
    code, raw = request("GET", "/api/wallets", headers=auth)
    wallets = json.loads(raw)
    check("默认现金钱包", code == 200 and wallets[0]["name"] == "现金", raw[:100])
    default_wallet = wallets[0]["id"]

    code, raw = request(
        "POST", "/api/wallets", {"name": "微信", "balance": 100}, headers=auth
    )
    check("新建钱包", code == 201, f"{code} {raw}")

    # ---------- 流水 ----------
    code, raw = request(
        "POST", "/api/transactions",
        {
            "category_id": expense_cat["id"],
            "wallet_id": default_wallet,
            "amount": 25.5,
            "type": "expense",
            "note": "午餐",
            "occurred_at": "2026-08-01",
        },
        headers=auth,
    )
    check("记一笔支出", code == 201, f"{code} {raw}")

    code, raw = request(
        "POST", "/api/transactions",
        {
            "category_id": income_cat["id"],
            "amount": 1500,
            "type": "income",
            "note": "八月生活费",
            "occurred_at": "2026-08-01",
        },
        headers=auth,
    )
    check("记一笔收入", code == 201, f"{code} {raw}")

    code, raw = request(
        "POST", "/api/transactions",
        {"category_id": expense_cat["id"], "amount": 10, "type": "income"},
        headers=auth,
    )
    check("类型/分类不匹配被拒", code == 400, f"{code} {raw}")

    code, raw = request("GET", "/api/transactions?page=1&page_size=10", headers=auth)
    page = json.loads(raw)
    check("分页返回", code == 200 and page["total"] == 2 and len(page["items"]) == 2, raw[:100])

    code, raw = request("GET", "/api/transactions?keyword=午餐", headers=auth)
    check("关键词搜索", code == 200 and json.loads(raw)["total"] == 1, raw[:100])

    # ---------- 预算 ----------
    code, raw = request("PUT", "/api/budget/2026-08", {"month": "2026-08", "amount": 1000}, headers=auth)
    check("设置预算", code == 200, f"{code} {raw}")
    code, raw = request("PUT", "/api/budget/2026-08", {"month": "2026-09", "amount": 1000}, headers=auth)
    check("预算月份不一致被拒", code == 400, f"{code} {raw}")

    # ---------- 统计 ----------
    for path in (
        "/api/stats/summary?month=2026-08",
        "/api/stats/trend?months=3",
        "/api/stats/monthly-summary?month=2026-08",
        "/api/stats/annual-report?year=2026",
    ):
        code, raw = request("GET", path, headers=auth)
        check(f"统计接口 {path.split('?')[0]}", code == 200, f"{code} {raw[:80]}")

    # ---------- 生活费 ----------
    code, raw = request("PUT", "/api/allowance", {"amount": 1500, "day_of_month": 1}, headers=auth)
    allow = json.loads(raw)
    check("设置生活费", code == 200 and allow["amount"] == 1500, f"{code} {raw}")
    check("生活费计算", allow["days_left"] > 0 and allow["daily_budget"] > 0, raw)

    # ---------- 导入 / 导出 ----------
    csv_data = "日期,类型,分类,金额,备注\n2026-08-03,支出,餐饮,18,奶茶\n"
    code, raw = request(
        "POST", "/api/transactions/import",
        files={"file": ("bill.csv", csv_data.encode(), "text/csv")},
        headers=auth,
    )
    imp = json.loads(raw)
    check("导入账单", code == 200 and imp["imported"] == 1, f"{code} {raw}")
    code, raw = request(
        "POST", "/api/transactions/import",
        files={"file": ("bill.csv", csv_data.encode(), "text/csv")},
        headers=auth,
    )
    check("重复导入去重", json.loads(raw)["skipped_duplicates"] == 1, raw)

    code, raw = request("GET", "/api/transactions/import-template")
    check("导入模板", code == 200 and "日期,类型" in raw, f"{code}")

    code, raw = request("GET", "/api/transactions/export?month=2026-08", headers=auth)
    check("导出 CSV", code == 200 and "奶茶" in raw, f"{code}")

    # ---------- 安全：无令牌访问 ----------
    code, _ = request("GET", "/api/transactions")
    check("无令牌被拒", code == 401, str(code))

    print(f"\n结果：通过 {total - failures} 项，失败 {failures} 项")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
