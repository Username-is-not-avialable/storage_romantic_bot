from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from api.config import get_settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


settings = get_settings()
SYNC_DATABASE_URL = settings.build_sync_database_url()
ASYNC_DATABASE_URL = settings.build_async_database_url()

engine = create_async_engine(ASYNC_DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    document = Column(String(100), nullable=True)
    role = Column(String(20), nullable=False, default="member")


class UserMessengerLink(Base):
    __tablename__ = "user_messenger_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(20), nullable=False)
    external_user_id = Column(String(255), nullable=False)
    linked_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    is_primary = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint("provider IN ('telegram', 'vk')", name="ck_user_messenger_links_provider"),
        UniqueConstraint("provider", "external_user_id", name="uq_user_messenger_links_provider_external"),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_token_hash = Column(String(128), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)


class VkLinkRequest(Base):
    __tablename__ = "vk_link_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)


class AuthEmailCode(Base):
    __tablename__ = "auth_email_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    email = Column(String(255), nullable=False)
    purpose = Column(String(30), nullable=False)
    code_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('email_verify', 'password_reset')",
            name="ck_auth_email_codes_purpose",
        ),
    )


class Gear(Base):
    __tablename__ = "gear"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    total_quantity = Column(Integer, nullable=False)
    available_count = Column(Integer, nullable=False)
    description = Column(String(500), nullable=True)


class Rental(Base):
    """Шапка аренды (документ): одна запись на выдачу с составом в rental_items."""

    __tablename__ = "rentals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    issue_manager_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    event = Column(String(300), nullable=False)
    comment = Column(String(300), nullable=True)
    status = Column(String(20), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (CheckConstraint("status IN ('active', 'closed')", name="ck_rentals_status"),)

    items = relationship("RentalItem", back_populates="rental", lazy="selectin")
    events = relationship("RentalEvent", back_populates="rental", lazy="selectin")


class RentalItem(Base):
    """Первоначальный состав выдачи по типу снаряжения."""

    __tablename__ = "rental_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rental_id = Column(Integer, ForeignKey("rentals.id", ondelete="CASCADE"), nullable=False)
    gear_id = Column(Integer, ForeignKey("gear.id"), nullable=False)
    qty_issued = Column(Integer, nullable=False)

    rental = relationship("Rental", back_populates="items")
    gear = relationship("Gear", lazy="joined")

    __table_args__ = (
        UniqueConstraint("rental_id", "gear_id", name="uq_rental_items_rental_gear"),
        CheckConstraint("qty_issued > 0", name="ck_rental_items_qty_issued_positive"),
    )


class RentalEvent(Base):
    """Append-only журнал событий по аренде."""

    __tablename__ = "rental_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rental_id = Column(Integer, ForeignKey("rentals.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    comment = Column(String(300), nullable=True)
    fee_status_snapshot = Column(String(20), nullable=True)

    rental = relationship("Rental", back_populates="events")
    lines = relationship("RentalEventItem", back_populates="rental_event", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "type IN ('ISSUE', 'RETURN_PARTIAL', 'RETURN_FINAL', 'CORRECTION')",
            name="ck_rental_events_type",
        ),
    )


class RentalEventItem(Base):
    """Строки возврата в рамках события RETURN_*."""

    __tablename__ = "rental_event_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rental_event_id = Column(
        Integer,
        ForeignKey("rental_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    gear_id = Column(Integer, ForeignKey("gear.id"), nullable=False)
    qty_returned = Column(Integer, nullable=False)
    damage_notes = Column(String(500), nullable=True)

    rental_event = relationship("RentalEvent", back_populates="lines")

    __table_args__ = (
        UniqueConstraint("rental_event_id", "gear_id", name="uq_rental_event_items_event_gear"),
        CheckConstraint("qty_returned > 0", name="ck_rental_event_items_qty_positive"),
    )


class RentalRequest(Base):
    __tablename__ = "rental_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # pending/approved/rejected
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)

    due_date = Column(Date, nullable=False)
    event = Column(String(300), nullable=False)
    comment = Column(String(300), nullable=True)

    deposit_document = Column(String(300), nullable=True)

    # Поля решения менеджера (для выборок и отображения)
    decision_manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    decision_comment = Column(String(300), nullable=True)


class RentalRequestItem(Base):
    __tablename__ = "rental_request_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rental_request_id = Column(Integer, ForeignKey("rental_requests.id"), nullable=False)
    gear_id = Column(Integer, ForeignKey("gear.id"), nullable=False)
    qty_requested = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("rental_request_id", "gear_id", name="uq_rental_request_gear"),
        CheckConstraint("qty_requested > 0", name="ck_rental_request_items_qty_positive"),
    )


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
