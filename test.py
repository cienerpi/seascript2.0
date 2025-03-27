from flask import Blueprint, render_template, session, redirect, url_for, request
from sqlalchemy import text
from app import db

tests_bp = Blueprint('tests', __name__, url_prefix='/tests')

# Константа: Bulk Carrier – Operational test id (например, 28)
TEST_ID_BULK_CARRIER_OP = 28

@tests_bp.route('/')
def start_test():
    """
    Запускает тест Bulk Carrier – Operational.
    Выбирает 50 случайных вопросов для теста с TEST_ID_BULK_CARRIER_OP и сохраняет их в сессию.
    """
    query = text("""
        SELECT id, question_text, answers, correct_answer_id, image 
        FROM questions 
        WHERE test_id = :tid 
        ORDER BY RANDOM() 
        LIMIT 50;
    """)
    result = db.session.execute(query, {'tid': TEST_ID_BULK_CARRIER_OP}).fetchall()
    if not result:
        return "No questions available for this test.", 404

    # Используем row._mapping для преобразования результата в словарь
    questions = [dict(row._mapping) for row in result]
    session['current_test_questions'] = questions
    session['current_question_index'] = 0
    session['score'] = 0
    session['incorrect_answers_ids'] = []
    return redirect(url_for('tests.show_question'))

@tests_bp.route('/question', methods=['GET', 'POST'])
def show_question():
    """
    Отображает текущий вопрос теста и обрабатывает ответ пользователя.
    Если все вопросы отвечены, отображает итоговый результат.
    """
    if 'current_test_questions' not in session or 'current_question_index' not in session:
        return redirect(url_for('tests.start_test'))

    questions = session['current_test_questions']
    index = session['current_question_index']
    total = len(questions)

    if index >= total:
        score = session.get('score', 0)
        return render_template('test_finished.html', score=score, total=total)

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

    return render_template('question.html', question=current_question, current=index+1, total=total)
