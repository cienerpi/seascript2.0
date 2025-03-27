import os
from dotenv import load_dotenv

# Принудительно загружаем .env (если файл существует)
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(dotenv_path):
    print(f"✅ .env найден: {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    print("❌ .env НЕ найден!")

class Config:
    # Конфигурационные параметры приложения
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")  # Используйте надежный ключ в продакшене
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    # Добавлено: настройки хранения сессий с помощью Flask-Session
    SESSION_TYPE = os.getenv("SESSION_TYPE", "filesystem")
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

# Убрано прямое отображение чувствительных данных (токен, URI) через print для безопасности.
# Логирование загрузки конфигурации выполняется при инициализации приложения.
