from datetime import datetime
from flask_login import UserMixin
from app import db
import uuid


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(64))
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    language_code = db.Column(db.String(10))
    profile_photo_url = db.Column(db.String(256))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.Integer, default=1)

    # Поле для сохранения последнего теста
    last_test_id = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f'<User {self.telegram_id} {self.username}>'


class TestResult(db.Model):
    __tablename__ = 'test_results'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False)  # Telegram ID пользователя
    test_id = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    correct_count = db.Column(db.Integer, nullable=False)
    incorrect_count = db.Column(db.Integer, nullable=False)
    incorrect_question_ids = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def save_test_result(user_id, test_id, score, total_questions, correct_count, incorrect_count, incorrect_question_ids):
    result = TestResult(
        user_id=user_id,
        test_id=test_id,
        score=score,
        total_questions=total_questions,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        incorrect_question_ids=incorrect_question_ids,
        created_at=datetime.utcnow()
    )
    db.session.add(result)
    db.session.commit()


class Test(db.Model):
    __tablename__ = 'tests'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    department = db.Column(db.Text, nullable=False)
    level = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Test {self.id} {self.name}>'


# Новая таблица для статистики пользователя и реферальной системы
import uuid
from datetime import datetime
from app import db


class UserStats(db.Model):
    __tablename__ = 'user_stats'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    referral_code = db.Column(db.String(32), unique=True, nullable=False, default=lambda: uuid.uuid4().hex[:8])
    referred_by = db.Column(db.Integer, nullable=True)  # Здесь будем хранить Telegram ID того, кто пригласил
    internal_currency = db.Column(db.Integer, default=20)
    experience = db.Column(db.Integer, default=0)

    user = db.relationship('User', backref=db.backref('stats', uselist=False))

    def __repr__(self):
        return f'<UserStats for user_id {self.user_id}>'

    def __repr__(self):
        return f'<UserStats for user_id {self.user_id}>'
