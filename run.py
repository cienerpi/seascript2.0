from app import create_app, db

app = create_app()

# Создаём структуру базы данных (таблицы) при старте
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Запускаем сервер на 0.0.0.0 (например, для доступа через ngrok)
    # В продакшене DEBUG должен быть отключён для безопасности
    app.run(host='0.0.0.0', port=5000, debug=True)
