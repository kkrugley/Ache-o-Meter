import pytest
import sys
sys.path.insert(0, '.')
import database as db


def test_feedback_table_sql_exists():
    """Таблица feedback должна быть определена в SQL."""
    assert 'feedback' in db.FEEDBACK_TABLE_SQL.lower()
    assert 'user_id' in db.FEEDBACK_TABLE_SQL
    assert 'forecast_date' in db.FEEDBACK_TABLE_SQL
    assert 'overall_feeling' in db.FEEDBACK_TABLE_SQL


def test_feedback_enabled_column_in_users_sql():
    """Миграция должна добавлять feedback_enabled."""
    # Проверяем что в MIGRATION_SQL есть колонка feedback_enabled
    assert 'feedback_enabled' in db.MIGRATION_SQL


def test_save_feedback_function_exists():
    """Функция save_feedback должна существовать и быть вызываемой."""
    assert callable(db.save_feedback)


def test_get_user_feedback_function_exists():
    """Функция get_user_feedback должна существовать и быть вызываемой."""
    assert callable(db.get_user_feedback)


def test_set_feedback_enabled_function_exists():
    """Функция set_feedback_enabled должна существовать и быть вызываемой."""
    assert callable(db.set_feedback_enabled)


def test_feedback_table_has_unique_constraint():
    """Таблица feedback должна иметь UNIQUE(user_id, forecast_date)."""
    assert 'UNIQUE(user_id, forecast_date)' in db.FEEDBACK_TABLE_SQL


def test_feedback_table_has_on_conflict_fields():
    """Таблица feedback должна содержать все поля симптомов."""
    required_fields = [
        'headache', 'joint_pain', 'fatigue',
        'respiratory', 'allergy_symptoms',
        'forecast_risk_score', 'forecast_risk_level',
        'pressure_change', 'temp_change', 'kp_max', 'pm25_avg'
    ]
    for field in required_fields:
        assert field in db.FEEDBACK_TABLE_SQL, f"Отсутствует поле: {field}"
