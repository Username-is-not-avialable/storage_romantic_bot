"""rental return requests (member-initiated return workflow)

Revision ID: 0007_rental_return_requests
Revises: 0006_vk_link_requests
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_rental_return_requests"
down_revision = "0006_vk_link_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rental_return_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rental_id", sa.Integer(), nullable=False),
        sa.Column("target_manager_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decision_manager_id", sa.Integer(), nullable=True),
        sa.Column("decision_comment", sa.String(length=300), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_rental_return_requests_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["rental_id"], ["rentals.id"]),
        sa.ForeignKeyConstraint(["target_manager_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["decision_manager_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "rental_return_request_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rental_return_request_id", sa.Integer(), nullable=False),
        sa.Column("gear_id", sa.Integer(), nullable=False),
        sa.Column("qty_return", sa.Integer(), nullable=False),
        sa.CheckConstraint("qty_return > 0", name="ck_rental_return_request_items_qty_positive"),
        sa.ForeignKeyConstraint(["gear_id"], ["gear.id"]),
        sa.ForeignKeyConstraint(
            ["rental_return_request_id"], ["rental_return_requests.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rental_return_request_id",
            "gear_id",
            name="uq_rental_return_request_items_req_gear",
        ),
    )
    op.create_index(
        "uq_rental_return_requests_one_pending_per_rental",
        "rental_return_requests",
        ["rental_id"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_rental_return_requests_one_pending_per_rental",
        table_name="rental_return_requests",
    )
    op.drop_table("rental_return_request_items")
    op.drop_table("rental_return_requests")
