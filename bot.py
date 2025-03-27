import logging
import os
import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from PIL import Image
# Разрешаем вложенные asyncio loop (актуально при повторном запуске в Jupyter и т.п.)
nest_asyncio.apply()

# Загружаем переменные окружения из .env (для отдельного запуска бота без Flask)
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импортируем Flask-приложение и модель для работы с БД внутри бота
from app import create_app, db
from app.models import User

# Инициализируем Flask-приложение и базу данных (для доступа к User внутри бота)
app = create_app()
app.app_context().push()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_user = update.effective_user
    user = User.query.filter_by(telegram_id=telegram_user.id).first()

    # Получаем свежие фото профиля
    photos = await context.bot.get_user_profile_photos(telegram_user.id)
    profile_photo_url = None
    if photos.total_count > 0:
        # Выбираем первый вариант первого фото
        photo = photos.photos[0][0]
        file = await context.bot.get_file(photo.file_id)

        # Определяем папку для сохранения аватара (app/static/uploads)
        uploads_dir = os.path.join("app", "static", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)

        # Формируем имя файла, например: avatar_452181463.jpg
        local_filename = os.path.join(uploads_dir, f"avatar_{telegram_user.id}.jpg")

        # Скачиваем файл
        await file.download_to_drive(custom_path=local_filename)

        # Открываем и изменяем размер изображения до минимального (например, ширина 50px)
        try:
            with Image.open(local_filename) as im:
                width = 50
                w_percent = (width / float(im.size[0]))
                height = int((float(im.size[1]) * float(w_percent)))
                im_resized = im.resize((width, height), Image.ANTIALIAS)
                im_resized.save(local_filename)
        except Exception as e:
            # Если произошла ошибка при изменении размера, логируем её и продолжаем
            print(f"Ошибка при изменении размера аватара: {e}")

        # Сохраняем относительный путь для использования в шаблоне (статическая папка app/static)
        profile_photo_url = f"uploads/avatar_{telegram_user.id}.jpg"

    if user:
        # Если пользователь уже существует, обновляем ссылку на аватар, если она изменилась
        if profile_photo_url and user.profile_photo_url != profile_photo_url:
            user.profile_photo_url = profile_photo_url
            db.session.commit()
        await update.message.reply_text(
            f"Привет, {telegram_user.first_name}! Вы уже зарегистрированы."
        )
    else:
        # Создаем нового пользователя, сохраняя актуальный аватар
        user = User(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code,
            profile_photo_url=profile_photo_url
        )
        db.session.add(user)
        db.session.commit()
        await update.message.reply_text(
            f"Привет, {telegram_user.first_name}! Вы успешно зарегистрированы."
        )

async def openweb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Формируем URL для WebApp (страница профиля)
    base_url = os.environ.get('NGROK_URL')
    if not base_url:
        logger.error("❌ NGROK_URL не установлен! Невозможно открыть мини-приложение.")
        await update.message.reply_text("Ошибка: URL приложения не настроен.")
        return
    webapp_url = base_url + "/profile"
    keyboard = [
        [InlineKeyboardButton(text="Open SeaScript WebApp", web_app=WebAppInfo(url=webapp_url))]
    ]
    await update.message.reply_text("Нажми кнопку, чтобы открыть WebApp:", reply_markup=InlineKeyboardMarkup(keyboard))
    logger.info(f"➡️ Пользователь ID={update.effective_user.id} выбрал команду /openweb (открытие WebApp)")

async def main():
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен в переменных окружения! Завершение работы бота.")
        return

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("openweb", openweb))

    # Оборачиваем вызов delete_webhook в try/except с таймаутом 10 секунд
    try:
        await application.bot.delete_webhook(timeout=10)
    except Exception as e:
        logger.warning(f"Не удалось удалить webhook: {e}")

    logger.info("🤖 Бот запущен. Ожидание сообщений (polling)...")
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
