from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from config import Config
import logging
from flask_login import LoginManager

db = SQLAlchemy()

def create_app():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    app = Flask(__name__)
    app.config.from_object(Config)

    # Проверяем, что TELEGRAM_BOT_TOKEN задан
    if not app.config.get("TELEGRAM_BOT_TOKEN"):
        logger.error("❌ Отсутствует TELEGRAM_BOT_TOKEN! Остановка запуска приложения.")
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for Telegram WebApp authentication")

    db.init_app(app)
    Session(app)

    # Настройка Flask‑Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "main.index"  # или другой маршрут, если есть страница логина

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        # Flask-Login требует функцию, которая возвращает пользователя по его ID
        return User.query.get(int(user_id))

    # (Опционально) добавляем current_user в шаблоны
    @app.context_processor
    def inject_user():
        from flask_login import current_user
        return dict(current_user=current_user)

    # Импорт и регистрация блюпринтов
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .tests.views import tests_bp
    app.register_blueprint(tests_bp)

    logger.info("✅ Конфигурация приложения загружена успешно")
    return app