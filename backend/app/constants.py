"""跨模块共享的常量。

为什么单独放一个模块：
「新用户注册」和「演示数据种子」都需要同一份默认分类，但后者不是路由。
如果常量留在 routers/auth.py，seed_demo.py 就得反向 import 路由包，
形成「非路由代码依赖路由层」的倒挂。放到这里两边都只依赖常量本身。
"""

# 新用户注册时自动创建的默认分类：(名称, 类型)
DEFAULT_CATEGORIES: list[tuple[str, str]] = [
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

# 新用户默认创建的钱包名（之后用户自己加微信/支付宝等）
DEFAULT_WALLET_NAME = "现金"

# AI 记账解析失败时的兜底分类名（保证流程不中断）
FALLBACK_EXPENSE_CATEGORY = "其他支出"
FALLBACK_INCOME_CATEGORY = "其他收入"
