import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
import os

# Конфигурация БД (замените на свои значения)

load_dotenv()
DB_CONFIG = {
    "host": os.getenv('DB_HOST'),
    "port": os.getenv('DB_PORT'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "database": os.getenv('DB_NAME')  # Будет создана если не существует
}


def create_database():
    """Создает БД, если она не существует"""
    try:
        # Подключаемся к серверу PostgreSQL без конкретной БД
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            dbname="postgres"  # Подключаемся к дефолтной БД
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Проверяем существование БД и создаем при необходимости
        cursor.execute(
            sql.SQL("SELECT 1 FROM pg_database WHERE datname = {}")
            .format(sql.Literal(DB_CONFIG["database"]))
        )
        if not cursor.fetchone():
            cursor.execute(
                sql.SQL("CREATE DATABASE {}")
                .format(sql.Identifier(DB_CONFIG["database"]))
            )
            print(f"БД {DB_CONFIG['database']} создана")
        else:
            print(f"БД {DB_CONFIG['database']} уже существует")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при создании БД: {e}")
        raise

def create_tables():
    """Создает таблицы в БД"""
    commands = (
        """
        CREATE TABLE IF NOT EXISTS users (
            id_telegram BIGINT PRIMARY KEY,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            document TEXT,
            is_manager BOOLEAN DEFAULT FALSE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS gear (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            total_quantity INTEGER NOT NULL CHECK (total_quantity >= 0),
            available_count INTEGER NOT NULL CHECK (available_count <= total_quantity),
            description TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS rentals (
            id SERIAL PRIMARY KEY,
            user_telegram_id BIGINT NOT NULL REFERENCES users(id_telegram),
            issue_manager_tg_id BIGINT NOT NULL REFERENCES users(id_telegram),
            accept_manager_tg_id BIGINT REFERENCES users(id_telegram),
            gear_id INTEGER NOT NULL REFERENCES gear(id),
            issue_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            due_date DATE NOT NULL,
            return_date DATE,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            event TEXT NOT NULL,
            comment TEXT,
            CHECK (due_date > issue_date::DATE),
            CHECK (return_date IS NULL OR return_date >= issue_date::DATE)
        )
        """
    )

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        for command in commands:
            cursor.execute(command)

        # Создаем индексы для ускорения поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rentals_user 
            ON rentals(user_telegram_id) 
            WHERE return_date IS NULL
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gear_name 
            ON gear(name)
        """)

        conn.commit()
        print("Таблицы и индексы созданы")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")
        raise

if __name__ == "__main__":
    print("Инициализация БД PostgreSQL...")
    create_database()
    create_tables()
    
    # Раскомментируйте для добавления тестовых данных
    # insert_test_data()
    
    print(f"Инициализация БД {DB_CONFIG['database']} завершена!")