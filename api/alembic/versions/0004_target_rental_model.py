"""target rental model: rentals header + rental_items + rental_events + rental_event_items

Revision ID: 0004_target_rental_model
Revises: 0003_rental_requests
Create Date: 2026-04-21

Migrates from flat `rentals` (one row per gear) to document model.
Legacy rows with partial returns stored only remaining qty in `quantity`; original
issued amount may be lost — migrated qty_issued equals legacy `quantity`.

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "0004_target_rental_model"
down_revision = "0003_rental_requests"
branch_labels = None
depends_on = None


_STATUS_CHECK = "status IN ('active', 'closed')"
_EVENT_TYPES = "type IN ('ISSUE', 'RETURN_PARTIAL', 'RETURN_FINAL', 'CORRECTION')"


def upgrade() -> None:
    op.rename_table("rentals", "rentals_legacy")

    op.create_table(
        "rentals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_manager_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("event", sa.String(length=300), nullable=False),
        sa.Column("comment", sa.String(length=300), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id_telegram"]),
        sa.ForeignKeyConstraint(["issue_manager_id"], ["users.id_telegram"]),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_rentals_status"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rental_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rental_id", sa.Integer(), nullable=False),
        sa.Column("gear_id", sa.Integer(), nullable=False),
        sa.Column("qty_issued", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["rental_id"], ["rentals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gear_id"], ["gear.id"]),
        sa.CheckConstraint("qty_issued > 0", name="ck_rental_items_qty_issued_positive"),
        sa.UniqueConstraint("rental_id", "gear_id", name="uq_rental_items_rental_gear"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rental_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rental_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("manager_id", sa.BigInteger(), nullable=True),
        sa.Column("comment", sa.String(length=300), nullable=True),
        sa.Column("fee_status_snapshot", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(["rental_id"], ["rentals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id_telegram"]),
        sa.CheckConstraint(_EVENT_TYPES, name="ck_rental_events_type"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rental_event_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rental_event_id", sa.Integer(), nullable=False),
        sa.Column("gear_id", sa.Integer(), nullable=False),
        sa.Column("qty_returned", sa.Integer(), nullable=False),
        sa.Column("damage_notes", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["rental_event_id"],
            ["rental_events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["gear_id"], ["gear.id"]),
        sa.CheckConstraint("qty_returned > 0", name="ck_rental_event_items_qty_positive"),
        sa.UniqueConstraint(
            "rental_event_id",
            "gear_id",
            name="uq_rental_event_items_event_gear",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_rental_items_rental_id", "rental_items", ["rental_id"])
    op.create_index("ix_rental_events_rental_id", "rental_events", ["rental_id"])
    op.create_index(
        "ix_rental_event_items_rental_event_id",
        "rental_event_items",
        ["rental_event_id"],
    )

    bind = op.get_bind()

    bind.execute(
        text(
            """
            INSERT INTO rentals (
                id, user_id, issue_manager_id, issue_date, due_date,
                event, comment, status, closed_at
            )
            SELECT
                id,
                user_id,
                issue_manager_id,
                issue_date,
                due_date,
                event,
                comment,
                CASE WHEN return_date IS NULL THEN 'active' ELSE 'closed' END,
                CASE
                    WHEN return_date IS NULL THEN NULL
                    ELSE (return_date::timestamp AT TIME ZONE 'UTC')
                END
            FROM rentals_legacy
            """
        )
    )

    bind.execute(
        text(
            """
            INSERT INTO rental_items (rental_id, gear_id, qty_issued)
            SELECT id, gear_id, quantity
            FROM rentals_legacy
            """
        )
    )

    bind.execute(
        text(
            """
            INSERT INTO rental_events (
                rental_id, type, created_at, manager_id, comment, fee_status_snapshot
            )
            SELECT
                id,
                'ISSUE',
                (issue_date::timestamp AT TIME ZONE 'UTC'),
                issue_manager_id,
                NULL,
                NULL
            FROM rentals_legacy
            """
        )
    )

    bind.execute(
        text(
            """
            INSERT INTO rental_events (
                rental_id, type, created_at, manager_id, comment, fee_status_snapshot
            )
            SELECT
                id,
                'RETURN_FINAL',
                (return_date::timestamp AT TIME ZONE 'UTC'),
                COALESCE(accept_manager_id, issue_manager_id),
                NULL,
                NULL
            FROM rentals_legacy
            WHERE return_date IS NOT NULL
            """
        )
    )

    bind.execute(
        text(
            """
            INSERT INTO rental_event_items (rental_event_id, gear_id, qty_returned)
            SELECT re.id, rl.gear_id, rl.quantity
            FROM rental_events re
            JOIN rentals_legacy rl ON rl.id = re.rental_id
            WHERE re.type = 'RETURN_FINAL'
            """
        )
    )

    bind.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('rentals', 'id'), "
            "COALESCE((SELECT MAX(id) FROM rentals), 1))"
        )
    )
    bind.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('rental_items', 'id'), "
            "COALESCE((SELECT MAX(id) FROM rental_items), 1))"
        )
    )
    bind.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('rental_events', 'id'), "
            "COALESCE((SELECT MAX(id) FROM rental_events), 1))"
        )
    )
    bind.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('rental_event_items', 'id'), "
            "COALESCE((SELECT MAX(id) FROM rental_event_items), 1))"
        )
    )

    op.drop_table("rentals_legacy")


def downgrade() -> None:
    op.drop_index("ix_rental_event_items_rental_event_id", table_name="rental_event_items")
    op.drop_index("ix_rental_events_rental_id", table_name="rental_events")
    op.drop_index("ix_rental_items_rental_id", table_name="rental_items")
    op.drop_table("rental_event_items")
    op.drop_table("rental_events")
    op.drop_table("rental_items")
    op.drop_table("rentals")

    op.create_table(
        "rentals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_manager_id", sa.BigInteger(), nullable=False),
        sa.Column("accept_manager_id", sa.BigInteger(), nullable=True),
        sa.Column("gear_id", sa.Integer(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=300), nullable=False),
        sa.Column("comment", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["gear_id"], ["gear.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id_telegram"]),
        sa.ForeignKeyConstraint(["issue_manager_id"], ["users.id_telegram"]),
        sa.ForeignKeyConstraint(["accept_manager_id"], ["users.id_telegram"]),
        sa.PrimaryKeyConstraint("id"),
    )
