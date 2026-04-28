from pathlib import Path
import subprocess
import sys

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from api.config import get_settings

settings = get_settings()
DB_CONFIG = {
    "host": settings.db_host,
    "port": settings.db_port,
    "user": settings.db_user,
    "password": settings.db_password,
    "database": settings.db_name,
}


def create_database() -> None:
    """Создает БД, если она не существует."""
    conn = psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        dbname=DB_CONFIG["database"],
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT 1 FROM pg_database WHERE datname = {}").format(
                    sql.Literal(DB_CONFIG["database"])
                )
            )
            if cursor.fetchone():
                print(f"БД {DB_CONFIG['database']} уже существует")
                return

            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(DB_CONFIG["database"])
                )
            )
            print(f"БД {DB_CONFIG['database']} создана")
    finally:
        conn.close()


def upgrade_schema() -> None:
    """
    Применяет актуальную схему через Alembic.
    """
    repo_root = Path(__file__).resolve().parents[1]
    alembic_ini = repo_root / "api" / "alembic.ini"
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", "head"],
        cwd=str(repo_root),
        check=True,
    )
    print("Схема БД обновлена до head через Alembic")


if __name__ == "__main__":
    print("Инициализация БД PostgreSQL...")
    create_database()
    upgrade_schema()
    print(f"Инициализация БД {DB_CONFIG['database']} завершена")