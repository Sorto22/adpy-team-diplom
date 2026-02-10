from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    VK_TOKEN = os.getenv("VK_TOKEN")  # Имя переменной, а не значение
    BOT_TOKEN = os.getenv("BOT_TOKEN")  # Имя переменной, а не значение
    POSTGRES_URI = os.getenv("POSTGRES_URI")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")