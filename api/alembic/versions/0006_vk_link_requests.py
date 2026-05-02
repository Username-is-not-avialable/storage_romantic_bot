"""vk_link_requests for VK web-to-bot linking

Revision ID: 0006_vk_link_requests
Revises: 0005_hard_user_auth_identity
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_vk_link_requests"
down_revision = "0005_hard_user_auth_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vk_link_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vk_link_requests_expires_at",
        "vk_link_requests",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vk_link_requests_expires_at", table_name="vk_link_requests")
    op.drop_table("vk_link_requests")
