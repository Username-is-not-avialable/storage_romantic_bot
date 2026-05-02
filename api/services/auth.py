from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import AuthEmailCode, AuthSession, User
from api.gmail_sender import send_email


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, stored_digest = password_hash.split("$", 1)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return secrets.compare_digest(digest, stored_digest)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalars().first()


async def create_session_for_user(session: AsyncSession, user_id: int) -> str:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(48)
    now = _utc_now()
    db_session = AuthSession(
        user_id=user_id,
        session_token_hash=hash_secret(raw_token),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.auth_session_ttl_hours),
    )
    session.add(db_session)
    await session.flush()
    return raw_token


async def resolve_user_by_session_token(session: AsyncSession, token: str) -> User | None:
    now = _utc_now()
    result = await session.execute(
        select(AuthSession).where(
            AuthSession.session_token_hash == hash_secret(token),
            AuthSession.expires_at > now,
        )
    )
    auth_session = result.scalars().first()
    if auth_session is None:
        return None

    auth_session.last_seen_at = now
    user = await session.get(User, auth_session.user_id)
    if user is None or not user.is_active:
        return None
    return user


async def revoke_session_token(session: AsyncSession, token: str) -> None:
    await session.execute(
        delete(AuthSession).where(AuthSession.session_token_hash == hash_secret(token))
    )


def build_auth_email_subject(purpose: str) -> str:
    if purpose == "email_verify":
        return "Код подтверждения email"
    return "Код восстановления пароля"


def build_auth_email_body(code: str, purpose: str) -> str:
    action = "подтверждения email" if purpose == "email_verify" else "сброса пароля"
    return (
        f"Ваш код для {action}: {code}\n\n"
        "Код действует ограниченное время. Если это были не вы, просто проигнорируйте письмо."
    )


async def request_email_code(session: AsyncSession, *, email: str, purpose: str) -> None:
    settings = get_settings()
    normalized_email = email.lower()
    user = await get_user_by_email(session, normalized_email)
    user_id = user.id if user else None

    code = f"{secrets.randbelow(1_000_000):06d}"
    now = _utc_now()

    session.add(
        AuthEmailCode(
            user_id=user_id,
            email=normalized_email,
            purpose=purpose,
            code_hash=hash_secret(code),
            created_at=now,
            expires_at=now + timedelta(minutes=settings.auth_code_ttl_minutes),
        )
    )
    await session.flush()
    send_email(
        to_email=normalized_email,
        subject=build_auth_email_subject(purpose),
        body=build_auth_email_body(code, purpose),
    )


async def _latest_code_query(email: str, purpose: str) -> Select[tuple[AuthEmailCode]]:
    return (
        select(AuthEmailCode)
        .where(
            AuthEmailCode.email == email.lower(),
            AuthEmailCode.purpose == purpose,
        )
        .order_by(AuthEmailCode.id.desc())
        .limit(1)
    )


async def verify_email_code(
    session: AsyncSession,
    *,
    email: str,
    purpose: str,
    code: str,
    new_password: str | None = None,
) -> bool:
    now = _utc_now()
    result = await session.execute(await _latest_code_query(email, purpose))
    db_code = result.scalars().first()
    if db_code is None:
        return False
    if db_code.used_at is not None or db_code.expires_at <= now:
        return False
    if not secrets.compare_digest(db_code.code_hash, hash_secret(code)):
        return False

    db_code.used_at = now
    user = await get_user_by_email(session, email)
    if user is not None:
        if purpose == "email_verify":
            user.email_verified_at = now
        elif purpose == "password_reset" and new_password:
            user.password_hash = hash_password(new_password)
    return True
