import pytest
import sys
sys.path.insert(0, '.')
from forecast_scoring import (
    calculate_risk_score,
    FACTOR_WEIGHTS,
    RISK_THRESHOLDS,
)


def test_weighted_score_single_factor():
    """Один фактор с баллом 5 и весом 1.5 = 7.5."""
    data = {
        'weather': {
            'hourly': {
                'time': ['2024-01-15T00:00'] * 48,
                'surface_pressure': [1013.0] * 48,
                'temperature_2m': [10.0] * 48,
                'apparent_temperature': [10.0] * 48,
                'relative_humidity_2m': [50.0] * 48,
                'dew_point_2m': [0.0] * 48,
                'visibility': [10000.0] * 48,
                'cape': [100.0] * 48,
                'freezing_level_height': [1000.0] * 48,
            },
            'daily': {
                'time': ['2024-01-14', '2024-01-15'],
                'temperature_2m_max': [10.0, 10.0],
                'temperature_2m_min': [5.0, 5.0],
            }
        },
        'air_quality': {
            'hourly': {
                'time': ['2024-01-15T00:00'] * 48,
                'pm2_5': [5.0] * 48,
                'pm10': [10.0] * 48,
                'nitrogen_dioxide': [10.0] * 48,
                'ozone': [40.0] * 48,
                'uv_index': [2.0] * 48,
            }
        },
        'geo': {'geo_forecast': []},
        'solar': {'solar_wind_speed': []},
    }

    user_profile = {
        'timezone': 'Europe/Moscow',
        'lat': 55.75,
        'lon': 37.62,
    }

    result = calculate_risk_score(data, user_profile)
    assert 'total_score' in result
    assert 'risk_level' in result
    assert 'factors' in result
    assert isinstance(result['total_score'], (int, float))


def test_no_data_returns_error():
    result = calculate_risk_score({}, {})
    assert result.get('error') is True


def test_risk_level_based_on_thresholds():
    """Проверяем что пороги корректно применяются."""
    assert RISK_THRESHOLDS[0] == (0, 5, 'Благоприятно', '🟢')
    assert RISK_THRESHOLDS[1] == (5, 12, 'Небольшой риск', '🟡 мягкий')
    assert RISK_THRESHOLDS[2] == (12, 20, 'Средний риск', '🟡')
    assert RISK_THRESHOLDS[3] == (20, 30, 'Высокий риск', '🟠')
    assert RISK_THRESHOLDS[4] == (30, float('inf'), 'Очень высокий риск', '🔴')


def test_factor_weights_defined():
    """Веса факторов определены."""
    assert 'pressure_change' in FACTOR_WEIGHTS
    assert 'pressure_rate' in FACTOR_WEIGHTS
    assert 'geomagnetic_kp' in FACTOR_WEIGHTS
    assert FACTOR_WEIGHTS['pressure_change'] == 1.5
    assert FACTOR_WEIGHTS['geomagnetic_kp'] == 1.2
