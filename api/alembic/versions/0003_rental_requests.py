"""add rental_requests and rental_request_items

Revision ID: 0003_rental_requests
Revises: 0002_user_roles
Create Date: 2026-04-02

"""

from alembic import op
import sqlalchemy as sa


revision = "0003_rental_requests"
down_revision = "0002_user_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rental_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "user_id", sa.BigInteger(), nullable=False
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("event", sa.String(length=300), nullable=False),
        sa.Column("comment", sa.String(length=300), nullable=True),
        sa.Column("deposit_document", sa.String(length=300), nullable=True),
        sa.Column(
            "decision_manager_id", sa.BigInteger(), nullable=True
        ),
        sa.Column("decision_comment", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id_telegram"]
        ),
        sa.ForeignKeyConstraint(
            ["decision_manager_id"], ["users.id_telegram"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rental_request_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rental_request_id", sa.Integer(), nullable=False),
        sa.Column("gear_id", sa.Integer(), nullable=False),
        sa.Column("qty_requested", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["gear_id"], ["gear.id"]
        ),
        sa.ForeignKeyConstraint(
            ["rental_request_id"], ["rental_requests.id"]
        ),
        sa.CheckConstraint("qty_requested > 0", name="ck_rental_request_items_qty_positive"),
        sa.UniqueConstraint(
            "rental_request_id",
            "gear_id",
            name="uq_rental_request_gear",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("rental_request_items")
    op.drop_table("rental_requests")

