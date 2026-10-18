"""baseline：把 create_all 建出来的库收敛到迁移管理之下

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-18

这是一支「收敛型」迁移，不是 autogenerate 出来的。

背景：项目早期用 SQLModel.metadata.create_all() 建表，本地与线上都已有数据。
按标准做法从空库生成迁移，已有库会因为表已存在直接失败。

所以这一支做三件事，都可重复执行：
1. 补建缺失的表；
2. 给已有表补上新增的列；
3. 建 alembic_version，从此版本号唯一。

之后每次改表都应该是正常的 autogenerate 迁移，不要再往这里加东西。
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _add_missing_columns(conn) -> None:
    from sqlmodel import SQLModel

    inspector = inspect(conn)
    existing = set(inspector.get_table_names())
    for table in SQLModel.metadata.sorted_tables:
        if table.name not in existing:
            continue  # create_all 已经建好，不用补列
        present = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column.type.compile(dialect=conn.dialect)}'
            default = getattr(column, "default", None)
            if default is not None and getattr(default, "is_scalar", False):
                value = default.arg
                if isinstance(value, bool):
                    ddl += f" DEFAULT {1 if value else 0}"
                elif isinstance(value, (int, float)):
                    ddl += f" DEFAULT {value}"
                elif isinstance(value, str):
                    ddl += " DEFAULT '{}'".format(value.replace("'", "''"))
            conn.execute(sa.text(ddl))


def upgrade() -> None:
    conn = op.get_bind()
    from sqlmodel import SQLModel

    SQLModel.metadata.create_all(bind=conn)
    _add_missing_columns(conn)


def downgrade() -> None:
    # 基线不回滚：删表等于删数据，交给人工判断
    pass
