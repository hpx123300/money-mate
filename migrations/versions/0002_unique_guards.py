"""unique guards：幂等的并发兜底 + 预算按月唯一

Revision ID: 0002_unique_guards
Revises: 0001_baseline
Create Date: 2026-10-19

为什么要这两条唯一索引：

1. `transaction(user_id, client_token)`
   幂等原来是纯应用层实现（先查有没有、没有再插入）。两个并发请求会同时查不到，
   各插一条——恰恰是双击、网络重试这种最该被幂等挡住的场景。加唯一索引后，
   后到的写入会抛 IntegrityError，写入侧回查并返回已有记录。

2. `budget(user_id, month)`
   预算也是「有就更新、没有就插入」，同样在并发下能插出两行，之后读侧 `first()`
   拿到哪一行取决于顺序。按月唯一把这条路径收敛成一个确定结果。

两支索引都可重复执行：先查 information_schema / sqlite_master，已存在就跳过。
client_token 允许 NULL，SQLite 与 MySQL 都不把多个 NULL 视为重复。
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_unique_guards"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def _index_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "uq_transaction_user_token" not in _index_names(inspector, "transaction"):
        op.create_index(
            "uq_transaction_user_token",
            "transaction",
            ["user_id", "client_token"],
            unique=True,
        )

    if "uq_budget_user_month" not in _index_names(inspector, "budget"):
        op.create_index(
            "uq_budget_user_month",
            "budget",
            ["user_id", "month"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "uq_transaction_user_token" in _index_names(inspector, "transaction"):
        op.drop_index("uq_transaction_user_token", table_name="transaction")

    if "uq_budget_user_month" in _index_names(inspector, "budget"):
        op.drop_index("uq_budget_user_month", table_name="budget")
