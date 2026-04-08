"""Shared utilities for Ache-o-Meter."""
from datetime import datetime
from zoneinfo import ZoneInfo


def parse_timezone_aware(time_str: str, timezone_str: str) -> datetime:
    """
    Парсит строку времени из Open-Meteo (naive) в aware datetime.
    Open-Meteo возвращает время в указанной timezone, но без суффикса.
    """
    dt = datetime.fromisoformat(time_str)
    if dt.tzinfo is not None:
        return dt  # уже aware
    tz = ZoneInfo(timezone_str)
    return dt.replace(tzinfo=tz)


def max_rate_of_change(values: list[float], timestamps: list[datetime], window_hours: int = 3) -> tuple[float, datetime | None]:
    """
    Находит максимальную скорость изменения в скользящем окне.
    Возвращает (max_rate, peak_time).
    """
    if not values or not timestamps or len(values) != len(timestamps):
        return 0.0, None

    max_rate = 0.0
    peak_time = None

    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            dt_hours = (timestamps[j] - timestamps[i]).total_seconds() / 3600
            if dt_hours > window_hours:
                break
            if dt_hours > 0:
                rate = abs(values[j] - values[i]) / dt_hours
                if rate > max_rate:
                    max_rate = rate
                    peak_time = timestamps[j]

    return max_rate, peak_time
