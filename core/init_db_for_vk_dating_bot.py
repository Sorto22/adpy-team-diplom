import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from config import Config


def create_database() -> None:
    """Создаёт базу данных vk_dating_bot_db в PostgreSQL, если она не существует.

    Подключается к серверу через суперпользователя и выполняет CREATE DATABASE.
    """
    try:
        conn = psycopg2.connect(
            host=Config().POSTGRES_HOST,
            port=Config().POSTGRES_PORT,
            user=Config().POSTGRES_USER,
            password=Config().POSTGRES_PASSWORD,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        cur = conn.cursor()

        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'vk_dating_bot_db'")
        exists = cur.fetchone()

        if not exists:
            cur.execute("CREATE DATABASE vk_dating_bot_db")
            print("✅ База данных 'vk_dating_bot_db' создана")
        else:
            print("ℹ️ База данных 'vk_dating_bot_db' уже существует")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    create_database()