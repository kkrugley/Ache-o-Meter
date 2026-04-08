import logging
import aiohttp
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import asyncio
import html
import pytz

from utils import parse_timezone_aware, max_rate_of_change
from solar_data import get_noaa_ap_index, get_solar_flares

# Re-export for backward compatibility (tests import from forecast)
__all__ = ['parse_timezone_aware', 'max_rate_of_change',
           'PARAMETER_DESCRIPTIONS', 'get_forecast_data', 'get_open_meteo_data',
           'get_air_quality_data', 'get_noaa_geo_data', 'get_solar_activity_data',
           'analyze_data_and_form_message', 'format_compact_message', 'format_detailed_message']

# Sentry SDK (опционально)
try:
    import sentry_sdk
    HAS_SENTRY = True
except ImportError:
    HAS_SENTRY = False

PARAMETER_DESCRIPTIONS = {
    "pressure": "<b>🌀 Атмосферное давление:</b> Резкие перепады давления — один из главных факторов, влияющих на самочувствие. Они могут вызывать головные боли и изменения артериального давления.",
    "temperature": "<b>🌡️ Температурные колебания:</b> Внезапные изменения температуры заставляют организм адаптироваться, что может быть стрессом, особенно для сердечно-сосудистой системы.",
    "humidity": "<b>💧 Влажность воздуха:</b> Изменения влажности влияют на дыхательную систему. Слишком высокая или низкая влажность может вызывать дискомфорт.",
    "geomagnetic": "<b>🌌 Геомагнитная активность:</b> Магнитные бури (высокий Kp-индекс) могут влиять на нервную и сердечно-сосудистую системы, вызывая общее недомогание.",
    "solar_activity": "<b>☀️ Солнечная активность:</b> Усиление солнечного ветра может косвенно влиять на геомагнитную обстановку Земли и, как следствие, на самочувствие.",
    "air_quality": "<b>🌫️ Качество воздуха:</b> Повышенные концентрации PM2.5, PM10, NO₂ и O₃ могут раздражать дыхательные пути и усугублять астму.",
    "uv_index": "<b>☀️ UV-излучение:</b> Высокий ультрафиолетовый индекс может вызывать головную боль, усталость и негативно влиять на кожу и глаза.",
    "pollen": "<b>🌿 Пыльца:</b> Высокая концентрация пыльцы в воздухе опасна для людей с сезонной аллергией (поллинозом).",
    "pressure_rate": "<b>⏱️ Скорость изменения давления:</b> Быстрые перепады давления за час (более 1 мм рт. ст./ч) особенно опасны для метеочувствительных.",
    "temperature_rate": "<b>⏱️ Скорость изменения температуры:</b> Резкие скачки температуры за час (более 2°C/ч) создают дополнительную нагрузку на организм.",
    "apparent_temperature": "<b>🌡️ Ощущаемая температура:</b> Разница между реальной и ощущаемой температурой (с учётом ветра и влажности) создаёт дополнительный стресс для организма.",
    "dew_point": "<b>💧 Точка росы:</b> Показатель влажности воздуха. Экстремальные значения (очень высокая или очень низкая точка росы) влияют на дыхание и терморегуляцию.",
    "visibility": "<b>🌫️ Видимость:</b> Низкая видимость (туман, смог, задымление) ухудшает качество воздуха и затрудняет дыхание.",
    "storm": "<b>⛈️ Грозовая активность:</b> Высокая конвективная энергия (CAPE) перед грозой связана с учащением мигреней и суставных болей.",
    "freezing_level": "<b>❄️ Уровень замерзания:</b> Резкие изменения высоты уровня замерзания могут влиять на суставы и сосуды у метеочувствительных людей.",
}

async def get_forecast_data(lat: float, lon: float):
    """
    Асинхронно собирает все необходимые данные о погоде, геомагнитной и солнечной активности,
    качестве воздуха и пыльце.
    Возвращает dict с РАЗДЕЛЬНЫМИ ключами для weather и air_quality.
    """
    weather_data, geo_data, solar_data, air_data, ap_data, flare_data = await asyncio.gather(
        get_open_meteo_data(lat, lon),
        get_noaa_geo_data(),
        get_solar_activity_data(),
        get_air_quality_data(lat, lon),
        get_noaa_ap_index(),
        get_solar_flares(),
    )
    return {
        'weather': weather_data,
        'air_quality': air_data,
        'geo': geo_data,
        'solar': solar_data,
        'ap': ap_data,
        'flares': flare_data,
    }


async def get_open_meteo_data(lat: float, lon: float):
    """
    Получает прогноз погоды (температура, давление, влажность, видимость, CAPE и др.) с Open-Meteo.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'temperature_2m,apparent_temperature,surface_pressure,relative_humidity_2m,dew_point_2m,visibility,cloudcover,cape,freezing_level_height',
        'daily': 'temperature_2m_max,temperature_2m_min',
        'forecast_days': 3,
        'timezone': 'auto'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                logging.info("Данные с Open-Meteo успешно получены.")
                return await response.json()
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка при запросе к Open-Meteo: {e}")
        if HAS_SENTRY:
            sentry_sdk.capture_exception(e)
    return {}


async def get_air_quality_data(lat: float, lon: float):
    """
    Получает данные о качестве воздуха (PM2.5, PM10, NO₂, O₃, UV, пыльца) с Open-Meteo Air Quality API.
    """
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'pm2_5,pm10,nitrogen_dioxide,ozone,uv_index,dust,alder_pollen,birch_pollen,grass_pollen,mugwort_pollen,olive_pollen,ragweed_pollen',
        'forecast_days': 3,
        'timezone': 'auto'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                logging.info("Данные о качестве воздуха с Open-Meteo успешно получены.")
                return await response.json()
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка при запросе к Open-Meteo Air Quality: {e}")
        if HAS_SENTRY:
            sentry_sdk.capture_exception(e)
    return {}


async def get_noaa_geo_data():
    """
    Получает прогноз геомагнитной активности (Kp-индекс) с NOAA SWPC.
    """
    url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                processed_data = [
                    {
                        'time_tag': item['time_tag'],
                        'kp_value': float(item['kp']),
                        'observation_status': item['observed']
                    }
                    for item in data if isinstance(item, dict) and 'time_tag' in item
                ]
                logging.info("Данные о геомагнитной обстановке с NOAA успешно получены.")
                return {'geo_forecast': processed_data}
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка при запросе к NOAA: {e}")
        if HAS_SENTRY:
            sentry_sdk.capture_exception(e)
    return {}


async def get_solar_activity_data():
    """
    Получает данные о солнечном ветре (скорость) как показатель солнечной активности.
    """
    url = "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                processed_data = [float(item[1]) for item in data[1:] if len(item) > 1 and item[1] != '-9999.9']
                logging.info("Данные о солнечной активности успешно получены.")
                return {'solar_wind_speed': processed_data}
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка при запросе к NOAA (solar wind): {e}")
        if HAS_SENTRY:
            sentry_sdk.capture_exception(e)
    return {}


# --- Анализ и формирование сообщения ---

def analyze_data_and_form_message(data: dict, user_profile: dict = None) -> dict:
    """
    Adapter: вызывает новую scoring-модель и возвращает результат.
    Обратная совместимость: добавляет 'risks' из factors для старого кода.
    """
    from forecast_scoring import calculate_risk_score

    result = calculate_risk_score(data, user_profile)

    if result.get('error'):
        return {"error": True}

    # Добавляем 'risks' для обратной совместимости с format_*_message
    risks = []
    for f in result.get('factors', []):
        if f['score'] > 0:
            level = 'Высокий' if f['score'] >= 7 else 'Средний' if f['score'] >= 4 else 'Низкий'
            risks.append((level, f['detail']))

    # Добавляем combo бонусы
    for c in result.get('combos', []):
        risks.append(('Бонус', f"🔗 {c['name']}: +{c['bonus']} балла"))

    result['risks'] = risks
    return result


# --- Форматирование сообщений ---

def format_compact_message(analysis: dict) -> str:
    """Формирует компактное сообщение с новым scoring."""
    if analysis.get('error'):
        return "Не удалось подготовить прогноз. Попробуйте позже. 🤷‍♂️"

    risk_level = analysis.get('risk_level', '')
    emoji = analysis.get('emoji', '🟢')
    total_score = analysis.get('total_score', 0)

    # Шкала 0-50
    bar_len = min(int(total_score / 50 * 10), 10)
    bar = '█' * bar_len + '░' * (10 - bar_len)

    message = f"{emoji} <b>Прогноз на сегодня</b>\n\n"
    message += f"Общий риск: {bar} {total_score}/50 — {risk_level.upper()}\n\n"

    # Топ-3 фактора
    factors = analysis.get('factors', [])
    top_factors = sorted(factors, key=lambda x: x['weighted'], reverse=True)[:3]
    if top_factors:
        message += "<b>⚠️ Главные факторы:</b>\n"
        for f in top_factors:
            message += f"{f['name']}: {f['detail']}\n"

    # Combo бонусы
    combos = analysis.get('combos', [])
    if combos:
        message += "\n<b>🔗 Комбинации:</b>\n"
        for c in combos:
            message += f"• {c['name']} (+{c['bonus']})\n"

    # Пиковое окно
    peak = analysis.get('peak_hours')
    if peak:
        message += f"\n⏰ Самое неприятное время: {peak}"

    return message


def format_detailed_message(analysis: dict) -> str:
    """Формирует развёрнутое сообщение с новым scoring."""
    if analysis.get('error'):
        return "Не удалось подготовить подробный прогноз. 🤷‍♂️"

    risk_level = analysis.get('risk_level', '')
    emoji = analysis.get('emoji', '🟢')
    total_score = analysis.get('total_score', 0)
    factors = analysis.get('factors', [])
    stats = analysis.get('stats', {})

    message = f"<b>📊 Подробный анализ</b>\n\n"
    message += f"Общий балл: {total_score} (из ~50 макс)\n"
    message += f"Уровень: {risk_level.upper()}\n\n"

    # Факторы с весами
    message += "<b>━━━ Факторы ━━━</b>\n"
    for f in factors:
        if f['score'] > 0:
            bar_len = min(int(f['score'] / 10 * 10), 10)
            bar = '█' * bar_len + '░' * (10 - bar_len)
            message += f"{f['name']}: {bar} {f['score']} ×{f['weight']} = {f['weighted']}\n"

    # Combo
    combos = analysis.get('combos', [])
    if combos:
        message += "\n<b>━━━ Комбинации ━━━</b>\n"
        for c in combos:
            message += f"  {c['name']} → +{c['bonus']} бонус\n"

    # Данные
    message += "\n<b>━━━ Данные ━━━</b>\n"
    if 'pressure_change_mmhg' in stats:
        direction = stats.get('pressure_direction', '')
        arrow = '↓' if 'falling' in direction else '↑'
        message += f"• Давление: {arrow} {stats['pressure_change_mmhg']} мм рт. ст."
        if 'pressure_rate_peak' in stats:
            message += f" (пик {stats['pressure_rate_peak']})"
        message += "\n"
    if 'kp_max' in stats:
        message += f"• Kp-индекс: макс {stats['kp_max']}\n"
    if 'humidity_avg' in stats:
        message += f"• Влажность: {stats['humidity_avg']}%\n"
    if 'pm25_avg' in stats:
        message += f"• PM2.5: {stats['pm25_avg']} мкг/м³ {'✅' if stats['pm25_avg'] <= 15 else '⚠️'}\n"
    if 'uv_max' in stats:
        message += f"• UV: макс {stats['uv_max']}\n"
    if 'temp_diff' in stats:
        message += f"• Температура: Δ{stats['temp_diff']}°C день-к-дню\n"

    message += "\n/info — подробнее о каждом факторе"
    return message
