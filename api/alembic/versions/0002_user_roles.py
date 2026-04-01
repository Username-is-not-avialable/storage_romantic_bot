"""add users.role and drop users.is_manager

Revision ID: 0002_user_roles
Revises: 0001_baseline
Create Date: 2026-04-01

"""

from alembic import op
import sqlalchemy as sa


revision = "0002_user_roles"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


_ROLE_CHECK = "role IN ('member', 'manager', 'admin')"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
    )
    op.create_check_constraint("ck_users_role", "users", _ROLE_CHECK)

    # No backward compatibility is required.
    op.drop_column("users", "is_manager")


def downgrade() -> None:
    op.add_column("users", sa.Column("is_manager", sa.Boolean(), nullable=True))
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")

