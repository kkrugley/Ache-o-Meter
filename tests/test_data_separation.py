import pytest
import asyncio
import sys
sys.path.insert(0, '.')
import forecast as fcst


class MockResponse:
    def __init__(self, json_data):
        self._json_data = json_data

    async def json(self):
        return self._json_data

    def raise_for_status(self):
        pass


@pytest.mark.asyncio
async def test_get_forecast_data_returns_separate_sources(monkeypatch):
    """get_forecast_data должен возвращать раздельные ключи, не merg'ить."""

    # Мокаем все API вызовы
    async def mock_weather(*args):
        return {
            'hourly': {
                'time': ['2024-01-15T00:00', '2024-01-15T01:00'],
                'temperature_2m': [10, 12],
                'surface_pressure': [1013, 1012],
            }
        }

    async def mock_air(*args):
        return {
            'hourly': {
                'time': ['2024-01-15T00:00', '2024-01-15T01:00'],
                'pm2_5': [8, 10],
                'pm10': [15, 18],
            }
        }

    async def mock_geo():
        return {'geo_forecast': []}

    async def mock_solar():
        return {'solar_wind_speed': []}

    monkeypatch.setattr(fcst, 'get_open_meteo_data', mock_weather)
    monkeypatch.setattr(fcst, 'get_air_quality_data', mock_air)
    monkeypatch.setattr(fcst, 'get_noaa_geo_data', mock_geo)
    monkeypatch.setattr(fcst, 'get_solar_activity_data', mock_solar)

    result = await fcst.get_forecast_data(52.0, 23.0)

    # Ключевое утверждение: данные НЕ должны быть смержены
    assert 'weather' in result, "Должен быть ключ 'weather'"
    assert 'air_quality' in result, "Должен быть ключ 'air_quality'"
    assert 'geo' in result, "Должен быть ключ 'geo'"
    assert 'solar' in result, "Должен быть ключ 'solar'"
    assert 'surface_pressure' not in result.get('hourly', {}), "hourly не должен содержать weather данные напрямую"
    assert 'geo_forecast' not in result, "geo_forecast не должен быть на верхнем уровне"
    assert result['weather']['hourly'].get('surface_pressure') is not None
    assert result['air_quality']['hourly'].get('pm2_5') is not None
    assert result['geo'].get('geo_forecast') is not None
    assert result['solar'].get('solar_wind_speed') is not None
