from flask import Blueprint, render_template, session, redirect, url_for, request
from sqlalchemy import text
from app import db
from app.models import save_test_result
from flask_login import current_user

tests_bp = Blueprint('tests', __name__, url_prefix='/tests')

@tests_bp.route('/')
def index():
    from flask_login import current_user
    last_test_name = None
    last_incorrect_count = 0
    last_result_id = None

    if current_user.is_authenticated:
        # Обновляем объект пользователя, чтобы получить актуальное last_test_id
        db.session.refresh(current_user)

        if current_user.last_test_id:
            from app.models import Test, TestResult

            # Находим тест, чтобы отобразить его название
            last_test = Test.query.get(current_user.last_test_id)
            if last_test:
                last_test_name = last_test.name

            # Находим последний результат для этого теста
            last_result = TestResult.query.filter_by(
                user_id=current_user.telegram_id,
                test_id=current_user.last_test_id
            ).order_by(TestResult.created_at.desc()).first()

            if last_result:
                last_incorrect_count = last_result.incorrect_count
                last_result_id = last_result.id

    return render_template(
        'tests/tests_index.html',
        last_test_name=last_test_name,
        last_incorrect_count=last_incorrect_count,
        last_result_id=last_result_id
    )

# Deck Department
@tests_bp.route('/deck')
def deck_levels():
    return render_template('tests/deck_levels.html')

@tests_bp.route('/deck/<string:level>')
def deck_by_level(level):
    # Допустимые уровни: operational, management, support, gmdss
    valid_levels = ['operational', 'management', 'support', 'gmdss']
    if level.lower() not in valid_levels:
        return "Invalid level", 400

    if level.lower() == 'gmdss':
        query_str = "SELECT id, name, level FROM tests WHERE department = 'deck' AND name ILIKE '%gmdss%' ORDER BY name;"
    else:
        query_str = f"SELECT id, name, level FROM tests WHERE department = 'deck' AND level = '{level.lower()}' ORDER BY name;"

    query = text(query_str)
    result = db.session.execute(query).fetchall()
    tests = [dict(row._mapping) for row in result]

    display_level = level.capitalize()
    return render_template('tests/deck_tests_by_level.html', tests=tests, level=display_level)


@tests_bp.route('/start_test/<int:test_id>')
def start_test_by_id(test_id):
    """
    Запускает выбранный тест (test_id):
      - выбирает 50 случайных вопросов и сохраняет их в сессию,
      - сохраняет test_id в last_test_id (если пользователь авторизован).
    """
    if current_user.is_authenticated:
        current_user.last_test_id = test_id
        db.session.commit()

    query = text("""
        SELECT id, question_text, answers, correct_answer_id, image 
        FROM questions 
        WHERE test_id = :tid 
        ORDER BY RANDOM() 
        LIMIT 50;
    """)
    result = db.session.execute(query, {'tid': test_id}).fetchall()
    if not result:
        return "No questions available for this test.", 404

    questions = [dict(row._mapping) for row in result]

    # Добавляем поле test_id в каждый вопрос
    for q in questions:
        q['test_id'] = test_id

    session['current_test_questions'] = questions
    session['current_question_index'] = 0
    session['score'] = 0
    session['incorrect_answers_ids'] = []
    session['current_test_id'] = test_id

    return redirect(url_for('tests.show_question'))


@tests_bp.route('/question', methods=['GET', 'POST'])
def show_question():
    if 'current_test_questions' not in session or 'current_question_index' not in session:
        return redirect(url_for('tests.index'))

    questions = session['current_test_questions']
    index = session['current_question_index']
    total = len(questions)

    if index >= total:
        score = session.get('score', 0)
        correct_count = score
        incorrect_count = total - score
        incorrect_ids = session.get('incorrect_answers_ids', [])
        test_id = session.get('current_test_id')

        # Обновляем last_test_id только если пользователь авторизован
        if current_user.is_authenticated:
            current_user.last_test_id = test_id
            db.session.commit()

        # Сохраняем результат теста
        save_test_result(
            current_user.telegram_id if current_user.is_authenticated else 0,
            test_id,
            score,
            total,
            correct_count,
            incorrect_count,
            incorrect_ids
        )
        # Передаем test_id и result_id (если используется) в шаблон
        # Здесь result_id можно получить, если функция save_test_result возвращает его,
        # или оставить как None, если не используется.
        result_id = None
        return render_template(
            'tests/test_finished.html',
            score=score,
            total=total,
            test_id=test_id,
            result_id=result_id
        )

    current_question = questions[index]

    if request.method == 'POST':
        try:
            selected = int(request.form.get('answer'))
        except (TypeError, ValueError):
            selected = 0

        if selected == current_question['correct_answer_id']:
            session['score'] += 1
        else:
            inc_ids = session.get('incorrect_answers_ids', [])
            inc_ids.append(current_question['id'])
            session['incorrect_answers_ids'] = inc_ids

        session['current_question_index'] = index + 1
        return redirect(url_for('tests.show_question'))

    return render_template('tests/question.html', question=current_question, current=index+1, total=total)

@tests_bp.route('/engine', endpoint='engine_tests')
def engine_tests():
    query = text("SELECT id, name, level FROM tests WHERE department = 'engine' ORDER BY level;")
    result = db.session.execute(query).fetchall()
    tests = [dict(row._mapping) for row in result]
    return render_template('tests/engine_tests.html', tests=tests)

@tests_bp.route('/start_test_incorrect/<int:result_id>')
def start_test_incorrect(result_id):
    if not current_user.is_authenticated:
        return redirect(url_for('tests.index'))

    from app.models import TestResult
    result = TestResult.query.get_or_404(result_id)

    # Проверка: результат должен принадлежать текущему пользователю
    if result.user_id != current_user.telegram_id:
        return "Unauthorized", 403

    incorrect_ids = result.incorrect_question_ids or []
    if not incorrect_ids:
        return "No incorrect questions in this test result.", 400

    query = text("""
        SELECT id, question_text, answers, correct_answer_id, image
        FROM questions
        WHERE id = ANY(:qids)
    """)
    result_questions = db.session.execute(query, {'qids': incorrect_ids}).fetchall()

    if not result_questions:
        return "No matching questions found for the incorrect IDs.", 400

    questions = [dict(row._mapping) for row in result_questions]

    session['current_test_questions'] = questions
    session['current_question_index'] = 0
    session['score'] = 0
    session['incorrect_answers_ids'] = []
    session['current_test_id'] = result.test_id

    return redirect(url_for('tests.show_question'))
