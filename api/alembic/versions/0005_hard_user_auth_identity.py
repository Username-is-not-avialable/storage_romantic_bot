"""hard switch to web auth identity and messenger links

Revision ID: 0005_hard_user_auth_identity
Revises: 0004_target_rental_model
Create Date: 2026-05-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "0005_hard_user_auth_identity"
down_revision = "0004_target_rental_model"
branch_labels = None
depends_on = None


def _remap_fk(bind, table: str, column: str, *, nullable: bool) -> None:
    op.add_column(table, sa.Column(f"{column}_new", sa.Integer(), nullable=True))
    bind.execute(
        text(
            f"""
            UPDATE {table} t
            SET {column}_new = u.id
            FROM users u
            JOIN user_messenger_links uml
              ON uml.user_id = u.id
             AND uml.provider = 'telegram'
            WHERE uml.external_user_id = t.{column}::text
            """
        )
    )
    op.drop_column(table, column)
    op.alter_column(
        table,
        f"{column}_new",
        new_column_name=column,
        nullable=nullable,
        existing_type=sa.Integer(),
    )


def upgrade() -> None:
    bind = op.get_bind()

    op.rename_table("users", "users_legacy")
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("document", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.CheckConstraint("role IN ('member', 'manager', 'admin')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "user_messenger_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("provider IN ('telegram', 'vk')", name="ck_user_messenger_links_provider"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_user_id", name="uq_user_messenger_links_provider_external"),
    )

    bind.execute(
        text(
            """
            INSERT INTO users (email, password_hash, email_verified_at, is_active, full_name, phone, document, role)
            SELECT
                CONCAT('tg_', id_telegram::text, '@local.invalid') AS email,
                '!' AS password_hash,
                NULL,
                TRUE,
                full_name,
                phone,
                document,
                role
            FROM users_legacy
            ORDER BY id_telegram
            """
        )
    )

    bind.execute(
        text(
            """
            INSERT INTO user_messenger_links (user_id, provider, external_user_id, is_primary)
            SELECT
                u.id,
                'telegram',
                ul.id_telegram::text,
                TRUE
            FROM users_legacy ul
            JOIN users u ON u.email = CONCAT('tg_', ul.id_telegram::text, '@local.invalid')
            """
        )
    )

    _remap_fk(bind, "rentals", "user_id", nullable=False)
    _remap_fk(bind, "rentals", "issue_manager_id", nullable=False)
    _remap_fk(bind, "rental_requests", "user_id", nullable=False)
    _remap_fk(bind, "rental_requests", "decision_manager_id", nullable=True)
    _remap_fk(bind, "rental_events", "manager_id", nullable=True)

    op.create_foreign_key("fk_rentals_user_id_users", "rentals", "users", ["user_id"], ["id"])
    op.create_foreign_key("fk_rentals_issue_manager_id_users", "rentals", "users", ["issue_manager_id"], ["id"])
    op.create_foreign_key("fk_rental_requests_user_id_users", "rental_requests", "users", ["user_id"], ["id"])
    op.create_foreign_key(
        "fk_rental_requests_decision_manager_id_users",
        "rental_requests",
        "users",
        ["decision_manager_id"],
        ["id"],
    )
    op.create_foreign_key("fk_rental_events_manager_id_users", "rental_events", "users", ["manager_id"], ["id"])

    op.drop_table("users_legacy")

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token_hash"),
    )
    op.create_table(
        "auth_email_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("purpose IN ('email_verify', 'password_reset')", name="ck_auth_email_codes_purpose"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("auth_email_codes")
    op.drop_table("auth_sessions")
    op.drop_table("user_messenger_links")
    op.drop_table("users")
