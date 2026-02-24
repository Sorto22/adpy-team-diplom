from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    """Конфигурация приложения.

    Загружает параметры из переменных окружения с помощью python-dotenv.
    """
    def __init__(self):
        """Инициализирует конфигурацию, загружая переменные окружения.

        Поля заполняются значениями из .env файла или переменных окружения.
        """
        self.VK_TOKEN = os.getenv("VK_TOKEN")
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.POSTGRES_URI = os.getenv("POSTGRES_URI")
        self.POSTGRES_HOST = os.getenv("POSTGRES_HOST")
        self.POSTGRES_PORT = os.getenv("POSTGRES_PORT")
        self.POSTGRES_USER = os.getenv("POSTGRES_USER")
        self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

    def validate(self) -> None:
        """Проверяет наличие всех необходимых переменных окружения.

        Raises:
            ValueError: Если хотя бы одна из обязательных переменных не задана.
        """
        REQUIRED_KEYS = ["VK_TOKEN", "BOT_TOKEN", "POSTGRES_HOST", "POSTGRES_PORT",
                         "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_URI"]
        empty_keys = [key for key in REQUIRED_KEYS if not os.getenv(key)]
        if empty_keys:
            raise ValueError(f"Не заданы переменные окружения: {', '.join(sorted(empty_keys))}")

config = Config()