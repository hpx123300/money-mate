#!/usr/bin/env python3
"""有数 的 MCP Server：让外部智能体（OpenClaw / Claude Desktop）能记账、查账。

设计上有个刻意的选择：**这里不重新实现业务，只是协议适配层**。

MCP 调的是本机已经在跑的 REST 接口。理由是记账的规则（幂等键、软删除、
金额精度、分类口径）都在业务层，如果在 MCP 里再写一遍"解析一句话"，
两套实现迟早会漂移——线上用 A，智能体用 B，数字对不上时没人能解释。

代价是需要服务先起来。对一个"跑在自己电脑上"的工具，这个代价可以接受；
真要做成远程服务，再把这一层换成直连数据库也不迟，接口契约已经在 REST 里定死了。

启动（服务需先运行在 127.0.0.1:8000）：
    MONEYMATE_USER=demo MONEYMATE_PASSWORD=demo123456 python mcp_server.py
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

BASE_URL = os.getenv("MONEYMATE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USERNAME = os.getenv("MONEYMATE_USER", "demo")
PASSWORD = os.getenv("MONEYMATE_PASSWORD", "demo123456")
TIMEOUT = float(os.getenv("MONEYMATE_TIMEOUT", "20"))

server = MCPServer(
    name="youshu",
    version="1.0.0",
    instructions=(
        "大学生花钱助手。用户说「午饭 25」「这个月花了多少」时用这里的工具。"
        "记账只生成草稿，不直接写库——要让用户在应用里确认，"
        "因为记错一笔的代价远高于多点一下。"
    ),
)

_token: str | None = None


def _raw(method: str, path: str, payload: dict | None = None, params: dict | None = None, form: dict | None = None):
    """一次 HTTP 调用。不用 httpx 是为了让这个文件零额外依赖——
    它是个协议适配层，装不装得上第三方库不该影响能不能跑。
    """
    url = f"{BASE_URL}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    if form is not None:
        # 登录走 OAuth2 表单格式，不是 JSON
        body = urllib.parse.urlencode(form).encode("utf-8")
        content_type = "application/x-www-form-urlencoded"
    else:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        content_type = "application/json"
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", content_type)
    if _token:
        req.add_header("Authorization", f"Bearer {_token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw[:200]}
    except urllib.error.URLError as exc:
        raise RuntimeError(f"连不上 {BASE_URL}：{exc.reason}（服务是否已启动？）") from exc


def _auth() -> None:
    """登录并缓存 token，顺带处理「过期了重登一次」。"""
    global _token
    if _token:
        return
    status, data = _raw(
        "POST", "/api/auth/login", form={"username": USERNAME, "password": PASSWORD}
    )
    if status != 200:
        raise RuntimeError(f"登录失败（{status}）：检查 MONEYMATE_USER / MONEYMATE_PASSWORD")
    # 兼容 OAuth2 标准的 access_token 与简写的 token 两种返回
    _token = data.get("access_token") or data.get("token")
    if not _token:
        raise RuntimeError(f"登录返回里没有 token：{data}")


def _get(path: str, params: dict | None = None):
    global _token
    _auth()
    status, data = _raw("GET", path, params=params)
    if status == 401:
        _token = None
        _auth()
        status, data = _raw("GET", path, params=params)
    if status >= 400:
        raise RuntimeError(f"{status}: {data.get('detail') or data}")
    return data


def _post(path: str, payload: dict):
    global _token
    _auth()
    status, data = _raw("POST", path, payload)
    if status == 401:
        _token = None
        _auth()
        status, data = _raw("POST", path, payload)
    if status >= 400:
        raise RuntimeError(f"{status}: {data.get('detail') or data}")
    return data


def _dump(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


@server.tool(description="把一句话解析成记账草稿（不写库）。例如「午饭 25」「昨天打车 18 块」。")
def parse_expense(text: str) -> str:
    if not text or not text.strip():
        return _dump({"error": "请说清楚花了多少"})
    try:
        data = _post("/api/ai/parse-transaction", {"text": text.strip()})
    except Exception as exc:  # noqa: BLE001
        return _dump({"error": str(exc)})
    return _dump(
        {
            "draft": data.get("items") or [],
            "multi": bool(data.get("multi")),
            "note": "草稿不会自动入账，需要用户在应用里确认后才会写入。",
        }
    )


@server.tool(description="查某个月的收支汇总：收入、支出、结余、分类占比。month 形如 2026-10，不传则本月。")
def query_spending(month: str = "") -> str:
    try:
        data = _get("/api/stats/summary", {"month": month} if month else None)
    except Exception as exc:  # noqa: BLE001
        return _dump({"error": str(exc)})
    return _dump(data)


@server.tool(description="查某个月的预算额度与使用情况。month 形如 2026-10，不传则本月。")
def get_budget(month: str = "") -> str:
    try:
        if month:
            data = _get(f"/api/budget/{month}")
        else:
            from datetime import date

            data = _get(f"/api/budget/{date.today():%Y-%m}")
    except Exception as exc:  # noqa: BLE001
        return _dump({"error": str(exc)})
    return _dump(data)


@server.tool(description="查生活费状态：总额、已花、剩余、日均可用、还能撑几天。")
def get_allowance_status() -> str:
    try:
        data = _get("/api/allowance")
    except Exception as exc:  # noqa: BLE001
        return _dump({"error": str(exc)})
    return _dump(data)


if __name__ == "__main__":
    server.run("stdio")
