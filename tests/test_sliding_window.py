import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
sys.path.insert(0, '.')
from forecast import max_rate_of_change


def test_max_rate_finds_peak_in_window():
    """Находит максимальную скорость в окне 3 часа."""
    base = datetime(2024, 1, 15, 0, 0, tzinfo=ZoneInfo("UTC"))
    times = [base + timedelta(hours=i) for i in range(6)]
    # Давление: резкий скачок между часами 1-2 (2.5 hPa за 1 час)
    values = [1013.0, 1013.5, 1016.0, 1016.5, 1017.0, 1017.5]  # в hPa

    max_rate, peak_time = max_rate_of_change(values, times, window_hours=3)

    # Скачок 2.5 hPa за 1 час = 2.5 hPa/h
    assert max_rate == pytest.approx(2.5, abs=0.1)
    assert peak_time == times[2]


def test_sliding_window_ignores_slow_changes():
    """Плавное изменение даёт низкую rate."""
    base = datetime(2024, 1, 15, 0, 0, tzinfo=ZoneInfo("UTC"))
    times = [base + timedelta(hours=i) for i in range(24)]
    values = [1013.0 + i * 0.2 for i in range(24)]  # плавный рост 0.2/h

    max_rate, _ = max_rate_of_change(values, times, window_hours=3)
    assert max_rate == pytest.approx(0.2, abs=0.05)


def test_empty_values_returns_zero():
    max_rate, peak = max_rate_of_change([], [], window_hours=3)
    assert max_rate == 0
    assert peak is None
