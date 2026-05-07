"""Наполнение PostgreSQL тестовыми данными (пользователи, снаряжение, аренды, заявки).

Использует переменные окружения DB_* (в Docker их задаёт `docker-compose.yml` для сервиса `api`;
локально — из `.env` в корне репозитория, как у приложения).

По умолчанию данные создаются один раз: если уже есть `member@seed.local`, скрипт выходит.
С `--force` сначала удаляются только seed-сущности:
  пользователи с email `*@seed.local`, снаряжение с именем `[seed] *`,
  связанные заявки и аренды.

Запуск в контейнере `api` (из корня репозитория, `WORKDIR` в образе — `/app`, каталог `scripts` смонтирован):

  docker compose exec api python scripts/seed_test_db.py
  docker compose exec api python scripts/seed_test_db.py --force

Локально с виртуальным окружением в репозитории:

  api/.venv/bin/python3 scripts/seed_test_db.py
  api/.venv/bin/python3 scripts/seed_test_db.py --force

Учётные записи после сида (пароли совпадают с тестами API):

  member@seed.local   / memberpass
  manager@seed.local  / managerpass
  admin@seed.local    / adminpass
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.database import (  # noqa: E402
    AsyncSessionLocal,
    Gear,
    Rental,
    RentalRequest,
    RentalRequestItem,
    User,
)
from api.services.auth import hash_password  # noqa: E402
from api.services.rental_requests import create_rental_request  # noqa: E402
from api.services.rentals import issue_rental, return_rental  # noqa: E402

SEED_EMAIL_SUFFIX = "@seed.local"
SEED_GEAR_PREFIX = "[seed] "


def _seed_emails() -> tuple[str, str, str]:
    return (
        f"member{SEED_EMAIL_SUFFIX}",
        f"manager{SEED_EMAIL_SUFFIX}",
        f"admin{SEED_EMAIL_SUFFIX}",
    )


async def _seed_user_ids(session: AsyncSession) -> list[int]:
    emails = _seed_emails()
    result = await session.execute(select(User.id).where(User.email.in_(emails)))
    return list(result.scalars().all())


async def clear_seed_data(session: AsyncSession) -> None:
    """Удаляет только данные с меткой seed (email / префикс снаряжения)."""
    uids = await _seed_user_ids(session)
    if not uids:
        return

    await session.execute(
        delete(RentalRequestItem).where(
            RentalRequestItem.rental_request_id.in_(
                select(RentalRequest.id).where(
                    (RentalRequest.user_id.in_(uids))
                    | (RentalRequest.decision_manager_id.in_(uids))
                )
            )
        )
    )
    await session.execute(
        delete(RentalRequest).where(
            (RentalRequest.user_id.in_(uids)) | (RentalRequest.decision_manager_id.in_(uids))
        )
    )
    await session.execute(
        delete(Rental).where(
            (Rental.user_id.in_(uids)) | (Rental.issue_manager_id.in_(uids))
        )
    )
    await session.execute(delete(User).where(User.id.in_(uids)))

    await session.execute(delete(Gear).where(Gear.name.startswith(SEED_GEAR_PREFIX)))
    await session.flush()


async def seed_if_needed(*, force: bool) -> None:
    member_email, manager_email, admin_email = _seed_emails()

    async with AsyncSessionLocal() as session:
        if force:
            await clear_seed_data(session)
            await session.commit()

        existing = await session.execute(select(User.id).where(User.email == member_email))
        if existing.scalar_one_or_none() is not None:
            print("Тестовые данные уже есть (member@seed.local). Используйте --force для пересоздания.")
            return

        member = User(
            email=member_email,
            password_hash=hash_password("memberpass"),
            email_verified_at=None,
            is_active=True,
            full_name="Тест Участник",
            phone="+79001001001",
            document="Паспорт 0000 000000",
            role="member",
        )
        manager = User(
            email=manager_email,
            password_hash=hash_password("managerpass"),
            email_verified_at=None,
            is_active=True,
            full_name="Тест Завснар",
            phone="+79001001002",
            document=None,
            role="manager",
        )
        admin = User(
            email=admin_email,
            password_hash=hash_password("adminpass"),
            email_verified_at=None,
            is_active=True,
            full_name="Тест Админ",
            phone="+79001001003",
            document=None,
            role="admin",
        )
        session.add_all([member, manager, admin])
        await session.flush()

        gear_specs: list[tuple[str, int, int, str]] = [
            (f"{SEED_GEAR_PREFIX}Ледоруб", 8, 6, "Классический ледоруб"),
            (f"{SEED_GEAR_PREFIX}Кошки альпийские", 12, 10, "Размер универсальный"),
            (f"{SEED_GEAR_PREFIX}Палатка 3-местная", 5, 4, "Трёхсезонная"),
        ]
        gears: list[Gear] = []
        for name, total, avail, desc in gear_specs:
            g = Gear(name=name, total_quantity=total, available_count=avail, description=desc)
            session.add(g)
            gears.append(g)
        await session.flush()

        g0, g1, g2 = gears
        today = date.today()
        due = today + timedelta(days=14)

        # Активная аренда у участника, оформлена завснаром
        await issue_rental(
            session=session,
            user_id=member.id,
            issue_manager_id=manager.id,
            due_date=due,
            event="Выходные в Хибинах",
            comment="Тестовая выдача",
            lines=[(g0.id, 1), (g1.id, 2)],
            fee_status_snapshot="active",
        )

        # Закрытая аренда: выдали и полностью вернули
        closed = await issue_rental(
            session=session,
            user_id=member.id,
            issue_manager_id=manager.id,
            due_date=due,
            event="Дневной поход",
            comment=None,
            lines=[(g2.id, 1)],
            issue_date=today - timedelta(days=30),
            fee_status_snapshot="active",
        )
        await return_rental(
            session=session,
            rental_id=closed.id,
            manager_id=manager.id,
            lines=[(g2.id, 1)],
            fee_status_snapshot="active",
            comment="Полный возврат (тест)",
        )

        # Заявка в очереди (pending)
        await create_rental_request(
            session=session,
            user_id=member.id,
            due_date=due + timedelta(days=7),
            event="Ледолазание (заявка)",
            comment="Тестовая заявка из seed",
            deposit_document="scan_zalog.pdf",
            target_manager_id=manager.id,
            items=[
                {"gear_id": g0.id, "qty_requested": 1},
                {"gear_id": g2.id, "qty_requested": 1},
            ],
        )

        await session.commit()

        print("Готово: созданы пользователи, снаряжение, аренды, заявка.")
        print(f"  Участник:  {member_email} / memberpass")
        print(f"  Завснар:   {manager_email} / managerpass")
        print(f"  Админ:     {admin_email} / adminpass")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Заполнить БД тестовыми данными (seed.local).")
    p.add_argument(
        "--force",
        action="store_true",
        help="Удалить предыдущие seed-данные и создать заново.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(seed_if_needed(force=args.force))


if __name__ == "__main__":
    main()
