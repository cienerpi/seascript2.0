import os
import logging
from flask import Blueprint, request, jsonify, session, current_app, render_template
from hashlib import sha256
import hmac
import json
from datetime import datetime

from app import db                 # Используем общий объект базы данных приложения
from app.models import User        # Импортируем модель пользователя

main = Blueprint('main', __name__)

logger = logging.getLogger(__name__)

# Маршрут API для авторизации через Telegram Mini App (WebApp)
@main.route('/auth', methods=['POST'])
def auth():
    data = request.get_json()
    if not data or 'initData' not in data:
        logger.warning("Авторизация: отсутствуют данные (initData) в запросе")
        return jsonify({'error': 'Отсутствуют данные авторизации'}), 400

    init_data = data['initData']
    logger.info(f"Получен запрос /auth, длина initData = {len(init_data)} символов")

    from urllib.parse import parse_qsl
    params_list = parse_qsl(init_data, keep_blank_values=True)
    params = {k: v for k, v in params_list}

    recv_hash = params.pop('hash', None)
    if not recv_hash:
        logger.warning("Авторизация: отсутствует параметр hash")
        return jsonify({'error': 'Некорректные данные авторизации'}), 400

    data_check_arr = [f"{k}={v}" for k, v in sorted(params.items())]
    data_check_string = "\n".join(data_check_arr)

    token = current_app.config['TELEGRAM_BOT_TOKEN']
    secret_key = hmac.new(b'WebAppData', token.encode('utf-8'), digestmod=sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode('utf-8'), digestmod=sha256).hexdigest()

    if calc_hash != recv_hash:
        logger.warning(f"Авторизация: хэш не совпадает (вычисленный: {calc_hash}, полученный: {recv_hash})")
        return jsonify({'error': 'Ошибка проверки подлинности данных'}), 403

    try:
        auth_date = int(params.get('auth_date', 0))
    except ValueError as e:
        logger.error(f"Авторизация: ошибка преобразования auth_date: {e}")
        auth_date = 0
    if auth_date == 0 or datetime.utcnow().timestamp() - auth_date > 24 * 3600:
        logger.warning(f"Авторизация: данные устарели или некорректны (auth_date={auth_date})")
        return jsonify({'error': 'Данные авторизации устарели'}), 403

    user_json = params.get('user')
    try:
        telegram_user = json.loads(user_json) if user_json else {}
        logger.info(f"Данные пользователя: {telegram_user}")
    except json.JSONDecodeError as e:
        logger.error(f"Авторизация: ошибка JSON при разборе поля user: {e}")
        return jsonify({'error': 'Некорректные данные пользователя'}), 400

    telegram_id = telegram_user.get('id')
    if not telegram_id:
        logger.error("Авторизация: отсутствует обязательный параметр id пользователя")
        return jsonify({'error': 'Некорректные данные пользователя'}), 400

    username = telegram_user.get('username')
    first_name = telegram_user.get('first_name')
    last_name = telegram_user.get('last_name')
    language_code = telegram_user.get('language_code')

    # Поиск или создание пользователя
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if user:
        logger.info(f"Пользователь с Telegram ID {telegram_id} найден, обновляем данные")
        # Сохраним текущее значение last_test_id, чтобы не потерять его
        last_test = user.last_test_id
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.language_code = language_code
        # Если у пользователя уже есть значение last_test_id, сохраняем его
        if last_test:
            user.last_test_id = last_test
    else:
        logger.info(f"Создание нового пользователя: Telegram ID {telegram_id}, username {username}")
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code
        )
        db.session.add(user)

    try:
        db.session.commit()
        logger.info(f"Данные пользователя (ID: {user.id}) успешно сохранены в БД")
    except Exception as e:
        logger.error(f"Ошибка при сохранении в БД: {e}")
        return jsonify({'error': 'Ошибка базы данных'}), 500

    from flask_login import login_user
    login_user(user)

    session['user_id'] = user.id
    session['telegram_id'] = user.telegram_id
    logger.info(f"Авторизация успешна для Telegram ID {telegram_id} (user.id: {user.id})")
    return jsonify({'status': 'ok'})



# Маршрут для отображения профиля пользователя
@main.route('/profile')
def profile():
    # Проверяем наличие пользователя в сессии
    current_user = None
    if 'user_id' in session:
        current_user = User.query.get(session['user_id'])
    if current_user:
        # Пользователь авторизован – рендерим профиль
        return render_template('profile.html', user=current_user)
    else:
        logger.info("🔒 Попытка доступа к /profile без авторизации")
        # Неавторизованный пользователь – возвращаем страницу с предложением авторизоваться
        return render_template('profile.html', user=None)

# Блок запуска приложения (__main__) удалён.
# Запуск веб-сервера осуществляется через файл run.py


@main.route('/vacancies')
def vacancies():
    return render_template('vacancies/index.html')

@main.route('/english')
def english():
    return render_template('english/index.html')

@main.route('/store')
def store():
    return render_template('store/index.html')