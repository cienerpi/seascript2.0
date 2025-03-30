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

# Импортируем Flask‑приложение и модели для работы с БД внутри бота
from app import create_app, db
from app.models import User, UserStats  # Импортируем модель User и дополнительную модель UserStats

# Инициализируем Flask‑приложение и базу данных (для доступа к User и UserStats)
app = create_app()
app.app_context().push()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_user = update.effective_user
    # Извлекаем реферальный параметр, если он передан, например "/start ABC123"
    message_text = update.message.text or ""
    parts = message_text.strip().split()
    referral_param = parts[1] if len(parts) > 1 else None

    user = User.query.filter_by(telegram_id=telegram_user.id).first()

    # Обработка аватара (оставляем тот же код)
    photos = await context.bot.get_user_profile_photos(telegram_user.id)
    profile_photo_url = None
    if photos.total_count > 0:
        photo = photos.photos[0][0]
        file = await context.bot.get_file(photo.file_id)
        uploads_dir = os.path.join("app", "static", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        local_filename = os.path.join(uploads_dir, f"avatar_{telegram_user.id}.jpg")
        await file.download_to_drive(custom_path=local_filename)
        try:
            with Image.open(local_filename) as im:
                width = 50
                w_percent = (width / float(im.size[0]))
                height = int((float(im.size[1]) * float(w_percent)))
                im_resized = im.resize((width, height), Image.Resampling.LANCZOS)
                im_resized.save(local_filename)
        except Exception as e:
            logger.error(f"Ошибка при изменении размера аватара: {e}")
        profile_photo_url = f"uploads/avatar_{telegram_user.id}.jpg"

    if user:
        if profile_photo_url and user.profile_photo_url != profile_photo_url:
            user.profile_photo_url = profile_photo_url
            db.session.commit()
        await update.message.reply_text(
            f"Привет, {telegram_user.first_name}! Вы уже зарегистрированы."
        )
    else:
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

        # Если передан реферальный параметр, ищем пользователя, чей referral_code совпадает,
        # и сохраняем его Telegram ID в поле referred_by
        inviter_id = None
        if referral_param:
            inviter_stats = UserStats.query.filter_by(referral_code=referral_param).first()
            if inviter_stats:
                inviter_id = inviter_stats.user.telegram_id  # или inviter_stats.user_id
                # Начисляем бонус пригласившему (например, 5 тугриков)
                inviter_stats.internal_currency += 5
                db.session.commit()

        # Создаем запись в UserStats для нового пользователя – реферальный код генерируется автоматически
        new_stats = UserStats(user_id=user.id, referred_by=inviter_id)
        db.session.add(new_stats)
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

    try:
        await application.bot.delete_webhook(timeout=10)
    except Exception as e:
        logger.warning(f"Не удалось удалить webhook: {e}")

    logger.info("🤖 Бот запущен. Ожидание сообщений (polling)...")
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
