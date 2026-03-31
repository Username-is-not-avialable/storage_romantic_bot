"""baseline migration: users, gear, rentals

Revision ID: 0001_baseline
Revises:
Create Date: 2026-03-30

"""

from alembic import op
import sqlalchemy as sa


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id_telegram", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("document", sa.String(length=100), nullable=True),
        sa.Column("is_manager", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id_telegram"),
    )

    op.create_table(
        "gear",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("total_quantity", sa.Integer(), nullable=False),
        sa.Column("available_count", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "rentals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_manager_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("accept_manager_tg_id", sa.BigInteger(), nullable=True),
        sa.Column("gear_id", sa.Integer(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=300), nullable=False),
        sa.Column("comment", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["gear_id"], ["gear.id"]),
        sa.ForeignKeyConstraint(["user_telegram_id"], ["users.id_telegram"]),
        sa.ForeignKeyConstraint(["issue_manager_tg_id"], ["users.id_telegram"]),
        sa.ForeignKeyConstraint(["accept_manager_tg_id"], ["users.id_telegram"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("rentals")
    op.drop_table("gear")
    op.drop_table("users")

