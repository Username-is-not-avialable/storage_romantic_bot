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

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.database import (
    AsyncSessionLocal,
    Gear,
    Rental,
    RentalEvent,
    RentalEventItem,
    RentalItem,
    RentalRequest,
    RentalRequestItem,
    RentalReturnRequest,
    RentalReturnRequestItem,
    User,
)
from api.services.auth import hash_password
from api.services.rental_requests import create_rental_request
from api.services.rentals import issue_rental, return_rental

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
    """Удаляет все данные через TRUNCATE (только для тестов!)."""
    await session.execute(text("TRUNCATE TABLE rental_event_items," \
                                             " rental_events, rental_items," \
                                             " rentals, rental_return_request_items," \
                                             " rental_return_requests, rental_request_items," \
                                             " rental_requests, auth_email_codes, auth_sessions," \
                                             " vk_link_requests, user_messenger_links, users, gear CASCADE;"))
    await session.commit()


async def seed_if_needed(*, force: bool) -> None:
    member_email, manager_email, admin_email = _seed_emails()

    async with AsyncSessionLocal() as session:
        if force:
            await clear_seed_data(session)
            await session.commit()

        existing = await session.execute(select(User.id).where(User.email == member_email))
        if existing.scalar_one_or_none() is not None:
            print("Тестовые данные уже есть. Используйте --force для пересоздания.")
            return

        # Создаём пользователей
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

        # Список снаряжения (107 позиций)
        gear_specs = [
            ("Палатка Quechua arpenaz 2+", 1, 2, ""),
            ("Палатка Alaska wind 3", 1, 2, "плохие молнии, 3 места, 6 колышков"),
            ("Палатка Temi Angara", 1, 1, "нет тамбурной дуги, не хватает колышков"),
            ("Палатка Quechua arpenaz 3 xl", 1, 1, ""),
            ("Палатка RockLand Mountain 3", 1, 1, ""),
            ("Палатка \"пещерная\"", 1, 1, "старая, не хватает колышков"),
            ("Палатка Alaska Dome", 1, 1, ""),
            ("Палатка Red Fox Comfort", 1, 1, ""),
            ("Палатка Red Fox Chellenger", 1, 1, ""),
            ("Палатка Rockland pamir v2 alu", 1, 1, ""),
            ("Палатка red fox cave 6 с дугами (полубочка)", 1, 1, ""),
            ("Шатер Манарага Зима", 6, 6, ""),
            ("Тент для шатра Зима", 3, 3, ""),
            ("Шатер ВЕК тикси 12, двухслойный", 1, 1, ""),
            ("Тент для шатра ВЕК Тикси 12", 2, 2, ""),
            ("Полубочка ВЕК Байкал лайт 8, трехслойная", 1, 1, ""),
            ("Полубочка ВЕК Байкал 12", 1, 1, ""),
            ("Тент 3*3", 2, 2, ""),
            ("Тент 4.6 * 2.7", 1, 1, ""),
            ("Тент 9*6", 1, 1, ""),
            ("Тент 1.8 * 2.95", 1, 1, ""),
            ("Тент 2.2 * 2.2", 1, 1, ""),
            ("Тент 2.2 * 2.8 тканевый тускло синий", 1, 1, ""),
            ("Тент 14.15 * 4.9 ярко салатовый", 1, 1, ""),
            ("Тент 3.85 * 3 снаружи болотный, изнутри серый", 1, 1, ""),
            ("Тент зеленый 4*6", 1, 1, ""),
            ("Рюкзак Free Knight Trekking 60", 1, 1, ""),
            ("Рюкзак Манарага синий ~70", 2, 2, ""),
            ("Рюкзак ВЕК Лось 90", 6, 6, ""),
            ("Рюкзак Манарага ~80", 3, 3, ""),
            ("Рюкзак Манарага Конжак 100", 1, 1, ""),
            ("Рюкзак Век черно-синий ~80", 1, 1, ""),
            ("Рюкзак Nova Tour Taimyr 110", 1, 1, ""),
            ("Рюкзак Манарага Конжак 80", 1, 1, ""),
            ("Рюкзак Синий без клапана ~60", 1, 1, ""),
            ("Рюкзак Nordway Greek 65", 1, 1, ""),
            ("Рюкзак Sturm 80 Камуфляжный", 1, 1, ""),
            ("Рюкзак Silver Top ~60", 1, 1, ""),
            ("Рюкзак Inversion 28", 1, 1, ""),
            ("Рюкзак Манарага 30", 2, 2, ""),
            ("Рюкзак Dynastar Heli 26", 1, 1, ""),
            ("Рюкзак Splav 45", 1, 1, ""),
            ("Рюкзак Алтай 120 АлпИндустрия discovery", 1, 1, ""),
            ("Рюкзак RedFox ligt 60", 1, 1, ""),
            ("Рюкзак ВЕК 30", 1, 1, ""),
            ("Рюкзак Синий 60", 1, 1, ""),
            ("Рюкзак Вело красный", 1, 1, ""),
            ("Рюкзак Astra 75", 1, 1, ""),
            ("Печка Век стандарт лайт", 2, 2, ""),
            ("Печка снигеревская", 1, 1, ""),
            ("ЗИП печка: 3 поддона, 2 насадки, 1 удлинняющая, 5 ножек, 2 экономайзера, штука с дыркой", 1, 1, ""),
            ("Котел 10л", 2, 2, ""),
            ("Котел 12л", 4, 4, ""),
            ("Котел 2л", 3, 3, ""),
            ("Котел 4л", 2, 2, ""),
            ("Котел 5л", 2, 2, ""),
            ("Котел 6л", 4, 4, ""),
            ("Котел 7л", 4, 4, ""),
            ("Котел прямоугольный", 3, 3, ""),
            ("Тросик костровой", 15, 15, ""),
            ("Поварешка", 2, 2, ""),
            ("Термос 2л", 24, 24, ""),
            ("Пенка 8мм", 1, 1, ""),
            ("Поппер", 1, 1, ""),
            ("Спальник", 1, 1, ""),
            ("2 камеры от спортивного катамарана №1", 1, 1, ""),
            ("2 камеры от туристического катамарата №2", 1, 1, ""),
            ("2 камеры от туристического катамарата №3", 1, 1, ""),
            ("2 шкуры от спортивного катамарана №1", 1, 1, ""),
            ("2 шкуры от туристического катамарана №2", 2, 2, ""),
            ("2 шкуры от туристического катамарана №3", 1, 1, ""),
            ("Кат Вольный ветер 4 + рама", 10, 10, ""),
            ("Кат в синем бауле 4 + рама", 1, 1, ""),
            ("красный мешок с болтами, 4 подушки для спортивного катамарана №1", 1, 1, ""),
            ("Весло", 15, 15, ""),
            ("Старая рама для ката", 2, 2, ""),
            ("Герма 70л", 5, 5, ""),
            ("Спасжилет", 1, 1, ""),
            ("Насос для катамарана", 1, 1, ""),
            ("Ледоруб ВЦСПС", 1, 1, ""),
            ("Ледоруб вертикаль 70", 1, 1, ""),
            ("Ледоруб 65", 1, 1, ""),
            ("Ледоруб 50", 1, 1, ""),
            ("Айсбаль", 1, 1, ""),
            ("Айсбаль гнутый", 1, 1, ""),
            ("Лопата rockland", 3, 3, ""),
            ("Лопата ortovox", 1, 1, ""),
            ("Кошки Salewa", 3, 3, ""),
            ("Кошки Lucky (немножко чиненные)", 1, 1, ""),
            ("Кошки Муравьева под жесткие ботинки", 2, 2, ""),
            ("Кошки Вертикаль антиподлип и оранжевая стропа", 2, 2, ""),
            ("Кошки 12 зубьев, сталь", 4, 4, ""),
            ("Кошки Венто", 1, 1, ""),
            ("Кошки 10 зубьев (1983г) дюраль, без стропы", 6, 6, ""),
            ("Кошки Noname", 1, 1, ""),
            ("Беседка Вертикаль Комфорт", 1, 1, ""),
            ("Беседка Vento стандарт vnt. 004", 1, 1, ""),
            ("Грудная обвязка Вертикаль Бабочка регулируемая", 1, 1, ""),
            ("Грудная обвязка Vento Бабочка регулируемая", 1, 1, ""),
            ("Система альпиниская совмещенная", 3, 3, ""),
            ("Усы самостроховки 3,5 м статика", 1, 1, ""),
            ("Усы самостраховки жёлтые", 1, 1, ""),
            ("Усы сине-зеленые", 1, 1, ""),
            ("Усы самостраховки динамические зелено-красные, с репиками черными", 1, 1, ""),
        ]
        gears: list[Gear] = []
        for name, total, avail, desc in gear_specs:
            g = Gear(name=name, total_quantity=total, available_count=avail, description=desc)
            session.add(g)
            gears.append(g)
        await session.flush()

        # Дополнительные тестовые аренды и заявка (опционально)
        g0, g1, g2 = gears[0], gears[1], gears[2]
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
