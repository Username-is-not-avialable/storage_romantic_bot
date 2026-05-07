"""rental_requests: target_manager_id (адресат уведомления)

Revision ID: 0008_rental_req_target_manager (≤32 симв. для alembic_version)
Revises: 0007_rental_return_requests
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_rental_req_target_mgr"
down_revision = "0007_rental_return_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rental_requests",
        sa.Column("target_manager_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_rental_requests_target_manager_id",
        "rental_requests",
        "users",
        ["target_manager_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_rental_requests_target_manager_id",
        "rental_requests",
        type_="foreignkey",
    )
    op.drop_column("rental_requests", "target_manager_id")
