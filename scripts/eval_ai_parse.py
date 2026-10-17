"""AI 一句话记账 · 字段级评测。

用法：
    .venv/bin/python scripts/eval_ai_parse.py                  # 全量 100 条
    .venv/bin/python scripts/eval_ai_parse.py --limit 10       # 先跑 10 条看看
    .venv/bin/python scripts/eval_ai_parse.py --repeat 5       # 额外做稳定性 Pass@5
    .venv/bin/python scripts/eval_ai_parse.py --save           # 结果存到 data/eval/results/
    .venv/bin/python scripts/eval_ai_parse.py --baseline <文件> # 与历史结果对比

为什么要这么测：
- 走的是真实的接口（POST /api/ai/parse-transaction），不是把提示词抄一份到脚本里。
  抄一份的话，评测能过而线上会挂，等于白测。
- 准确率拆到字段级。金额错和日期错是严重程度完全不同的两种错，
  混成一个「整句准确率」看不出问题在哪。
- 用临时数据库，不碰开发数据；评测只读，不写任何流水。

口径（什么算对）写在 data/eval/parse_cases.json 头部，改数据集要同步改口径。
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

# ---- 环境必须在 import app.* 之前固定：settings 是模块级单例，导入即读死 ----
_TMP_DB = Path(tempfile.gettempdir()) / "moneymate_eval.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["APP_ENV"] = "test"       # 跳过演示数据播种
os.environ["REDIS_URL"] = ""         # 强制内存缓存，评测不受本机 Redis 影响
# 注意：这里不覆盖 LLM_API_KEY，评测就是要真实调用模型

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.constants import DEFAULT_CATEGORIES  # noqa: E402
from app.database import engine, init_db  # noqa: E402
from app.models import Category, User, Wallet  # noqa: E402
from app.routers import ai as ai_router  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402

CASES_PATH = ROOT / "data" / "eval" / "parse_cases.json"
RESULTS_DIR = ROOT / "data" / "eval" / "results"

# 钱包顺序要和演示账号一致（微信在最前），否则兜底行为会和线上不一样
EVAL_WALLETS = ["微信", "支付宝", "现金"]


def _fail(msg: str) -> None:
    print(f"评测无法开始：{msg}")
    sys.exit(2)


def setup_client() -> TestClient:
    """建临时库 + 评测用户 + 令牌，返回可用的 TestClient 与请求头。"""
    init_db()
    with Session(engine) as s:
        user = User(
            username="evaluser",
            email="eval@example.com",
            hashed_password=hash_password("evalpass123"),
        )
        s.add(user)
        s.flush()
        for name, ctype in DEFAULT_CATEGORIES:
            s.add(Category(user_id=user.id, name=name, type=ctype))
        for name in EVAL_WALLETS:
            s.add(Wallet(user_id=user.id, name=name, balance=0))
        s.commit()
        user_id = user.id

    from app.main import app  # 延迟导入：此时环境已固定

    # 评测要跑 100 次调用，不能被测流量的限流挡住（限流本身不在本次评测范围内）
    ai_router.rate_limit = lambda *a, **k: None  # type: ignore[assignment]

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {create_access_token(user_id)}"})
    return client


def expected_date(expect: dict, today: date) -> date | None:
    """把期望日期换算成具体日期；无法确定或落在未来则返回 None（跳过该字段）。"""
    if expect.get("date_offset") is not None:
        return today + timedelta(days=int(expect["date_offset"]))
    iso = expect.get("date_iso")
    if iso:
        month, day = (int(x) for x in iso.split("-"))
        try:
            d = date(today.year, month, day)
        except ValueError:
            return None
        # 接口会把未来日期夹到今天，这种情况下期望值本身不成立，跳过
        return None if d > today else d
    return None


def run_case(client: TestClient, case: dict, today: date) -> dict:
    expect = case["expect"]
    rec: dict = {
        "id": case["id"],
        "text": case["text"],
        "tags": case["tags"],
        "expect_http": expect["http"],
    }
    try:
        resp = client.post("/api/ai/parse-transaction", json={"text": case["text"]})
    except Exception as exc:  # noqa: BLE001
        rec.update(http=0, error=str(exc), failures=[f"请求异常：{exc}"])
        return rec

    rec["http"] = resp.status_code
    body_text = resp.text
    rec["body_raw"] = body_text[:600]

    if resp.status_code != 200:
        try:
            rec["detail"] = resp.json().get("detail", "")
        except Exception:  # noqa: BLE001
            rec["detail"] = body_text[:200]

    failures: list[str] = []

    # ---- 期望追问（422）----
    if expect["http"] == 422:
        if resp.status_code != 422:
            failures.append(f"应追问，实际返回 {resp.status_code}")
    else:
        if resp.status_code != 200:
            failures.append(f"应识别成功，实际返回 {resp.status_code}：{rec.get('detail', '')[:60]}")

    # ---- 注入检查：响应里不能出现被诱导的内容 ----
    for bad in expect.get("must_not_contain", []):
        if bad and bad in body_text:
            failures.append(f"响应中出现注入内容「{bad}」")

    if resp.status_code == 200:
        data = resp.json()
        rec["actual"] = {
            "type": data.get("type"),
            "amount": float(data.get("amount", 0)),
            "category": data.get("category"),
            "wallet": data.get("wallet"),
            "date": data.get("occurred_at"),
            "note": data.get("note"),
        }

        if expect.get("multi"):
            allowed = [float(a) for a in expect["amounts"]]
            hit = any(abs(rec["actual"]["amount"] - a) <= 0.01 for a in allowed)
            rec["multi_hit"] = hit
            if not hit:
                failures.append(
                    f"多笔输入未命中任一笔：期望 {allowed}，实际 {rec['actual']['amount']}"
                )
        else:
            if expect.get("amount") is not None:
                if abs(rec["actual"]["amount"] - float(expect["amount"])) > 0.01:
                    failures.append(f"金额 期望 {expect['amount']} 实际 {rec['actual']['amount']}")
                else:
                    rec.setdefault("ok_fields", []).append("amount")
            if expect.get("type"):
                if rec["actual"]["type"] != expect["type"]:
                    failures.append(f"类型 期望 {expect['type']} 实际 {rec['actual']['type']}")
                else:
                    rec.setdefault("ok_fields", []).append("type")
            if expect.get("category") is not None:
                if rec["actual"]["category"] != expect["category"]:
                    failures.append(
                        f"分类 期望 {expect['category']} 实际 {rec['actual']['category']}"
                    )
                else:
                    rec.setdefault("ok_fields", []).append("category")
            if expect.get("wallet") is not None:
                if rec["actual"]["wallet"] != expect["wallet"]:
                    failures.append(f"钱包 期望 {expect['wallet']} 实际 {rec['actual']['wallet']}")
                else:
                    rec.setdefault("ok_fields", []).append("wallet")
            want_date = expected_date(expect, today)
            if want_date is not None:
                if rec["actual"]["date"] != want_date.isoformat():
                    failures.append(f"日期 期望 {want_date} 实际 {rec['actual']['date']}")
                else:
                    rec.setdefault("ok_fields", []).append("date")
            elif expect.get("date_offset") is not None or expect.get("date_iso"):
                rec["date_skipped"] = True

    rec["failures"] = failures
    rec["passed"] = not failures
    return rec


def field_has_expectation(f: str, expect: dict, rec: dict) -> bool:
    """该样本对某字段是否有明确期望。

    没有明确期望的样本必须排除出分母——否则「没评测」会被算成「没通过」，
    准确率会被系统性拉低，看起来像模型的问题，其实是数据集的问题。
    """
    if f == "date":
        if rec.get("date_skipped"):
            return False
        return expect.get("date_offset") is not None or bool(expect.get("date_iso"))
    return expect.get(f) is not None


def compute(records: list[dict], cases: dict[str, dict], today: date) -> dict:
    total = len(records)
    status = Counter(r["http"] for r in records)

    # 字段分母：只算「实际返回 200 且该字段有明确期望」的样本
    fields = ["type", "amount", "category", "wallet", "date"]
    field_total: dict[str, int] = defaultdict(int)
    field_ok: dict[str, int] = defaultdict(int)

    for r in records:
        if r["http"] != 200:
            continue
        expect = cases[r["id"]]["expect"]
        if expect.get("multi"):
            continue
        ok = set(r.get("ok_fields", []))
        for f in fields:
            if not field_has_expectation(f, expect, r):
                continue
            field_total[f] += 1
            if f in ok:
                field_ok[f] += 1

    # 追问正确率
    should_ask = [r for r in records if r["expect_http"] == 422]
    asked = [r for r in should_ask if r["http"] == 422]
    # 多笔样本本来就不支持，它返回 422 不计入「过度追问」
    over_asked = [
        r
        for r in records
        if r["expect_http"] == 200
        and r["http"] == 422
        and not cases[r["id"]]["expect"].get("multi")
    ]

    # 分类混淆矩阵
    confusion: Counter = Counter()
    for r in records:
        if r["http"] != 200 or "actual" not in r:
            continue
        expect_cat = cases[r["id"]]["expect"].get("category")
        if expect_cat:
            actual_cat = r["actual"]["category"]
            if actual_cat != expect_cat:
                confusion[(expect_cat, actual_cat)] += 1

    # 多笔
    multi = [r for r in records if cases[r["id"]]["expect"].get("multi")]
    multi_hit = [r for r in multi if r.get("multi_hit")]

    # 对抗
    adversarial = [r for r in records if "对抗" in r["tags"]]
    adv_clean = [r for r in adversarial if not any("注入内容" in f for f in r["failures"])]

    errors = [r for r in records if r["http"] not in (200, 422)]

    return {
        "total": total,
        "status": dict(status),
        "field_total": dict(field_total),
        "field_ok": dict(field_ok),
        "should_ask": len(should_ask),
        "asked": len(asked),
        "over_asked": len(over_asked),
        "confusion": {f"{k[0]} → {k[1]}": v for k, v in confusion.most_common()},
        "multi_total": len(multi),
        "multi_hit": len(multi_hit),
        "adversarial_total": len(adversarial),
        "adversarial_clean": len(adv_clean),
        "errors": len(errors),
    }


def pct(ok: int, total: int) -> str:
    return f"{ok / total * 100:5.1f}%" if total else "    —"


def print_report(summary: dict, records: list[dict], meta: dict, cases: dict[str, dict]) -> None:
    print("=" * 62)
    print("AI 一句话记账 · 字段级评测")
    print("=" * 62)
    print(f"数据集：{meta['dataset']}（{summary['total']} 条）")
    print(f"模型：{meta['model']}    时间：{meta['time']}")
    print()

    print("一、请求结果")
    print(f"  返回 200（识别成功）  {summary['status'].get(200, 0):>3}")
    print(f"  返回 422（追问金额）  {summary['status'].get(422, 0):>3}")
    if summary["errors"]:
        print(f"  服务/模型错误         {summary['errors']:>3}")
    print(f"  该追问且追问了        {summary['asked']}/{summary['should_ask']}  "
          f"（{pct(summary['asked'], summary['should_ask'])}）")
    if summary["over_asked"]:
        print(f"  过度追问（有金额却追问）{summary['over_asked']:>3} 条")
    print()

    print("二、字段准确率（分母＝实际返回 200 且该字段有明确期望的样本）")
    names = {"type": "类型", "amount": "金额", "category": "分类", "wallet": "钱包", "date": "日期"}
    for f in ["type", "amount", "category", "wallet", "date"]:
        t, o = summary["field_total"].get(f, 0), summary["field_ok"].get(f, 0)
        print(f"  {names[f]}    {pct(o, t)}   ({o}/{t})")
    print()

    print("三、分类混淆（只列错的）")
    if summary["confusion"]:
        for k, v in summary["confusion"].items():
            print(f"  {k}    {v} 次")
    else:
        print("  无")
    print()

    print("四、多笔输入（当前实现只返回一笔，单独统计不并入准确率）")
    print(f"  命中任意一笔   {summary['multi_hit']}/{summary['multi_total']}")
    for r in records:
        if r.get("multi_hit") is not None:
            mark = "命中" if r["multi_hit"] else "漏掉"
            actual = r.get("actual", {}).get("amount", "—")
            print(f"    {r['id']}  {mark}  返回 {actual}  ← {r['text']}")
        elif cases[r["id"]]["expect"].get("multi") and r["http"] == 422:
            print(f"    {r['id']}  直接追问（多笔被当成无法解析）  ← {r['text']}")
    print()

    print("五、对抗样本（是否被注入指令带跑）")
    print(f"  响应未出现注入内容   {summary['adversarial_clean']}/{summary['adversarial_total']}")
    print()

    failed = [r for r in records if not r["passed"]]
    print(f"六、未通过明细（{len(failed)} 条）")
    if not failed:
        print("  全部通过")
    for r in failed:
        print(f"  {r['id']}  {r['text']}")
        for f in r["failures"]:
            print(f"        {f}")
    print()


def run_stability(client: TestClient, cases: list[dict], today: date, repeat: int) -> None:
    """稳定性：对同一输入重复跑 repeat 次，看结果是否稳定。

    大模型输出有随机性，一次通过不代表稳定通过。
    配合 --only 可以对某几条重点样本单独测。
    """
    sample = [c for c in cases if not c["expect"].get("multi")][:8]
    print(f"七、稳定性 Pass@{repeat}（抽样 {len(sample)} 条，每条重复 {repeat} 次）")
    for case in sample:
        runs = [run_case(client, case, today) for _ in range(repeat)]
        all_ok = sum(1 for r in runs if r["passed"])
        detail = ""
        if all_ok != repeat:
            detail = "  失败原因：" + "；".join(sorted({f for r in runs for f in r["failures"]})[:2])
        print(f"  {case['id']}  通过 {all_ok}/{repeat}  {'稳定' if all_ok == repeat else '不稳定'}{detail}")
    print()


def print_comparison(baseline_path: Path, summary: dict) -> None:
    try:
        base = json.loads(baseline_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"（读取基线失败：{exc}）")
        return
    b = base.get("summary", {})
    print("八、与基线对比")
    for f in ["type", "amount", "category", "wallet", "date"]:
        bt, bo = b.get("field_total", {}).get(f, 0), b.get("field_ok", {}).get(f, 0)
        nt, no = summary["field_total"].get(f, 0), summary["field_ok"].get(f, 0)
        if not bt or not nt:
            continue
        delta = (no / nt - bo / bt) * 100
        print(f"  {f:<10} {bo / bt * 100:5.1f}% → {no / nt * 100:5.1f}%   {delta:+.1f} 个百分点")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="AI 一句话记账字段级评测")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条，用于快速验证")
    ap.add_argument("--only", type=str, default="", help="只跑指定 id，逗号分隔，如 --only c098,c032")
    ap.add_argument("--repeat", type=int, default=0, help="额外做稳定性 Pass@k")
    ap.add_argument("--save", action="store_true", help="把结果保存到 data/eval/results/")
    ap.add_argument("--baseline", type=str, default="", help="与指定的历史结果文件对比")
    args = ap.parse_args()

    from app.config import settings

    if not settings.llm_api_key:
        _fail("未配置 LLM_API_KEY，评测需要真实调用模型。请在 .env 里填好再跑。")

    dataset = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = dataset["cases"]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in wanted]
        if not cases:
            _fail(f"--only 没有匹配到任何用例：{args.only}")
    if args.limit:
        cases = cases[: args.limit]

    today = date.today()
    client = setup_client()

    print(f"开始评测：{len(cases)} 条，模型 {settings.llm_model}（逐条调用，约需 {len(cases) * 3 // 60 + 1} 分钟）\n")
    records: list[dict] = []
    for i, case in enumerate(cases, 1):
        rec = run_case(client, case, today)
        records.append(rec)
        mark = "ok  " if rec["passed"] else "FAIL"
        print(f"  [{i:>3}/{len(cases)}] {mark} {case['id']}  {case['text'][:26]}", flush=True)

    print()
    case_map = {c["id"]: c for c in cases}
    summary = compute(records, case_map, today)

    meta = {
        "dataset": str(CASES_PATH.relative_to(ROOT)),
        "model": settings.llm_model,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "limit": args.limit or None,
    }
    print_report(summary, records, meta, case_map)

    if args.repeat:
        run_stability(client, cases, today, args.repeat)

    if args.baseline:
        print_comparison(Path(args.baseline), summary)

    if args.save:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"{datetime.now():%Y-%m-%d_%H%M}.json"
        out.write_text(
            json.dumps({"meta": meta, "summary": summary, "records": records}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"结果已保存：{out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
