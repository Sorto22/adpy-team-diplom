from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    def __init__(self):
        self.VK_TOKEN = os.getenv("VK_TOKEN")  # Имя переменной, а не значение
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")  # Имя переменной, а не значение
        self.POSTGRES_URI = os.getenv("POSTGRES_URI")
        self.POSTGRES_HOST = os.getenv("POSTGRES_HOST")
        self.POSTGRES_PORT = os.getenv("POSTGRES_PORT")
        self.POSTGRES_USER = os.getenv("POSTGRES_USER")
        self.POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

    def validate(self):
        REQUIRED_KEYS = ["VK_TOKEN", "BOT_TOKEN", "POSTGRES_HOST", "POSTGRES_PORT",
                         "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_URI"]
        empty_keys = [key for key in REQUIRED_KEYS if not os.getenv(key)]
        if len(empty_keys) >0 :
            raise ValueError(f"Не заданы переменные окружения: {', '.join([f'{k}'for k in sorted (empty_keys)])}")

config = Config()