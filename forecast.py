import logging
import aiohttp
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import asyncio
import html
import pytz

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
    weather_data, geo_data, solar_data, air_data = await asyncio.gather(
        get_open_meteo_data(lat, lon),
        get_noaa_geo_data(),
        get_solar_activity_data(),
        get_air_quality_data(lat, lon),
    )
    return {
        'weather': weather_data,
        'air_quality': air_data,
        'geo': geo_data,
        'solar': solar_data,
    }


async def get_open_meteo_data(lat: float, lon: float):
    """
    Получает прогноз погоды (температура, давление, влажность, видимость, CAPE и др.) с Open-Meteo.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'temperature_2m,apparent_temperature,surface_pressure,relative_humidity_2m,dew_point_2m,visibility,cloud_cover_total,cape,freezing_level_height',
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


# --- Анализ и формирование сообщения ---

def analyze_data_and_form_message(data: dict, user_profile: dict = None):
    """
    Анализирует собранные данные и возвращает dict с рисками и статистикой.
    Учитывает профиль пользователя (чувствительность, аллергены).
    """
    if not data:
        return {"error": True}

    # Определяем, какие факторы учитывать
    sensitivities = {
        'pressure': True,
        'temperature': True,
        'humidity': True,
        'geomagnetic': True,
        'air_quality': True,
        'uv': True,
        'apparent_temperature': True,
        'dew_point': True,
        'visibility': True,
        'storm': True,
        'freezing_level': True,
    }
    allergens = {
        'alder': False,
        'birch': False,
        'grass': False,
        'mugwort': False,
        'olive': False,
        'ragweed': False,
    }
    if user_profile:
        for key in sensitivities:
            db_key = f'sensitivity_{key}' if key != 'uv' else 'sensitivity_uv'
            if db_key in user_profile:
                sensitivities[key] = bool(user_profile[db_key])
        for key in allergens:
            db_key = f'allergen_{key}'
            if db_key in user_profile:
                allergens[key] = bool(user_profile[db_key])

    # Получаем timezone пользователя
    user_tz = "UTC"  # default
    if user_profile and user_profile.get('timezone'):
        user_tz = user_profile['timezone']

    risks = []
    now = datetime.now(ZoneInfo(user_tz))
    has_allergen_sensitivity = any(allergens.values())

    # Статистика для детального отчёта
    stats = {}

    # Разделяем источники данных
    weather_hourly = data.get('weather', {}).get('hourly', {})
    weather_times = weather_hourly.get('time', [])
    air_hourly = data.get('air_quality', {}).get('hourly', {})
    air_times = air_hourly.get('time', [])

    # 1. Анализ Атмосферного давления
    if sensitivities['pressure']:
        try:
            hourly_pressure = weather_hourly.get('surface_pressure', [])
            hourly_times = weather_times
            if hourly_pressure and hourly_times:
                past_24h = []
                future_24h = []
                for t, p in zip(hourly_times, hourly_pressure):
                    try:
                        dt = parse_timezone_aware(t, user_tz)
                        if now - timedelta(hours=24) <= dt < now:
                            past_24h.append((dt, p))
                        elif now <= dt < now + timedelta(hours=24):
                            future_24h.append((dt, p))
                    except (ValueError, TypeError):
                        continue

                if past_24h and future_24h:
                    hpa_to_mmhg = 0.750062
                    min_past = min(p for _, p in past_24h)
                    max_future = max(p for _, p in future_24h)
                    pressure_change_24h = (max_future - min_past) * hpa_to_mmhg

                    stats['pressure_min'] = round(min(p for _, p in past_24h + future_24h) * hpa_to_mmhg, 1)
                    stats['pressure_max'] = round(max(p for _, p in past_24h + future_24h) * hpa_to_mmhg, 1)
                    stats['pressure_change_24h'] = round(pressure_change_24h, 1)

                    if abs(pressure_change_24h) > 10:
                        risks.append(("Высокий", f"очень резкий перепад давления (изменение на {round(pressure_change_24h)} мм рт. ст. за сутки)"))
                    elif abs(pressure_change_24h) > 5:
                        risks.append(("Средний", f"заметный перепад давления (изменение на {round(pressure_change_24h)} мм рт. ст. за сутки)"))
                    else:
                        stats['pressure_status'] = '✅ норма'

                    # Скорость изменения давления (мм рт. ст./час) — скользящее окно 3 часа
                    if len(past_24h) >= 2:
                        all_pressure_points = sorted(past_24h + future_24h, key=lambda x: x[0])
                        pressure_values_mmhg = [p * hpa_to_mmhg for _, p in all_pressure_points]
                        pressure_times = [t for t, _ in all_pressure_points]

                        max_pressure_rate, pressure_peak = max_rate_of_change(
                            pressure_values_mmhg, pressure_times, window_hours=3
                        )
                        stats['pressure_rate'] = round(max_pressure_rate, 2)
                        if pressure_peak:
                            stats['pressure_peak_time'] = pressure_peak.strftime('%H:%M')
                        if max_pressure_rate > 1.5:
                            risks.append(("Высокий", f"очень быстрое изменение давления ({round(max_pressure_rate, 1)} мм рт. ст./час)"))
                        elif max_pressure_rate > 1.0:
                            risks.append(("Средний", f"быстрое изменение давления ({round(max_pressure_rate, 1)} мм рт. ст./час)"))
                        else:
                            stats['pressure_rate_status'] = '✅ норма'

                    # Пиковый час риска по давлению
                    if future_24h:
                        peak_dt, peak_val = max(future_24h, key=lambda x: x[1])
                        min_dt, min_val = min(future_24h, key=lambda x: x[1])
                        max_change_val = max(
                            abs(peak_val - min_past) * hpa_to_mmhg,
                            abs(min_val - min_past) * hpa_to_mmhg
                        )
                        if max_change_val > 3:
                            peak_time_str = peak_dt.strftime('%H:%M') if abs(peak_val - min_past) > abs(min_val - min_past) else min_dt.strftime('%H:%M')
                            stats['pressure_peak_time'] = peak_time_str
                            risks.append(("Инфо", f"пиковый час по давлению: ~{peak_time_str}"))
        except (KeyError, IndexError, TypeError) as e:
            logging.warning(f"Не удалось проанализировать давление: {e}")

    # 2. Анализ Температурных колебаний
    if sensitivities['temperature']:
        try:
            daily_temp = data.get('weather', {}).get('daily', {})
            if daily_temp.get('temperature_2m_max'):
                today_max = daily_temp['temperature_2m_max'][1] if len(daily_temp['temperature_2m_max']) > 1 else daily_temp['temperature_2m_max'][0]
                yesterday_max = daily_temp['temperature_2m_max'][0]
                temp_diff = abs(today_max - yesterday_max)
                stats['temp_today_max'] = round(today_max, 1)
                stats['temp_yesterday_max'] = round(yesterday_max, 1)
                stats['temp_diff'] = round(temp_diff, 1)

                if temp_diff > 10:
                    risks.append(("Высокий", f"очень резкое изменение температуры (на {round(temp_diff)}°C по сравнению со вчерашним днём)"))
                elif temp_diff > 5:
                    risks.append(("Средний", f"заметное изменение температуры (на {round(temp_diff)}°C по сравнению со вчерашним днём)"))
                else:
                    stats['temp_status'] = '✅ норма'

                # Скорость изменения температуры
                hourly_temp = weather_hourly.get('temperature_2m', [])
                hourly_times = weather_times
                if hourly_temp and hourly_times and len(hourly_temp) >= 2:
                    recent = []
                    for t, temp in zip(hourly_times, hourly_temp):
                        try:
                            dt = parse_timezone_aware(t, user_tz)
                            if now - timedelta(hours=6) <= dt <= now:
                                recent.append((dt, temp))
                        except (ValueError, TypeError):
                            continue
                    if len(recent) >= 2:
                        sorted_recent = sorted(recent, key=lambda x: x[0])
                        time_span = (sorted_recent[-1][0] - sorted_recent[0][0]).total_seconds() / 3600
                        if time_span > 0:
                            temp_rate = abs(sorted_recent[-1][1] - sorted_recent[0][1]) / time_span
                            stats['temp_rate'] = round(temp_rate, 2)
                            if temp_rate > 2.0:
                                risks.append(("Средний", f"быстрое изменение температуры ({round(temp_rate, 1)}°C/час)"))
                            else:
                                stats['temp_rate_status'] = '✅ норма'
        except (KeyError, IndexError, TypeError) as e:
            logging.warning(f"Не удалось проанализировать температуру: {e}")

    # 3. Анализ Влажности
    if sensitivities['humidity']:
        try:
            hourly_humidity = weather_hourly.get('relative_humidity_2m', [])
            hourly_times = weather_times
            if hourly_humidity and hourly_times:
                past_24h_humidity = []
                for t, h in zip(hourly_times, hourly_humidity):
                    try:
                        dt = parse_timezone_aware(t, user_tz)
                        if now - timedelta(hours=24) <= dt < now:
                            past_24h_humidity.append(h)
                    except (ValueError, TypeError):
                        continue
                if past_24h_humidity:
                    avg_humidity = sum(past_24h_humidity) / len(past_24h_humidity)
                    stats['humidity_avg'] = round(avg_humidity, 1)
                    if avg_humidity > 85:
                        risks.append(("Низкий", "очень высокая влажность воздуха"))
                    elif avg_humidity < 30:
                        risks.append(("Низкий", "очень низкая влажность воздуха"))
                    else:
                        stats['humidity_status'] = '✅ норма'
        except (KeyError, IndexError, TypeError) as e:
            logging.warning(f"Не удалось проанализировать влажность: {e}")

    # 4. Анализ Геомагнитной активности (Kp-индекс)
    if sensitivities['geomagnetic']:
        try:
            geo_forecast = data.get('geo', {}).get('geo_forecast', [])
            future_limit = datetime.now(pytz.UTC) + timedelta(hours=24)
            max_kp = 0
            for forecast in geo_forecast:
                forecast_time = datetime.fromisoformat(forecast['time_tag'].replace('Z', '+00:00'))
                if forecast_time < future_limit and forecast['kp_value'] > max_kp:
                    max_kp = forecast['kp_value']

            stats['kp_max'] = int(max_kp) if max_kp else 0

            if max_kp >= 7:
                risks.append(("Высокий", f"сильная магнитная буря (Kp-индекс до {int(max_kp)})"))
            elif max_kp >= 5:
                risks.append(("Средний", f"магнитная буря (Kp-индекс до {int(max_kp)})"))
            elif max_kp >= 4:
                risks.append(("Низкий", f"повышенная геомагнитная активность (Kp-индекс до {int(max_kp)})"))
            else:
                stats['kp_status'] = '✅ норма'
        except Exception as e:
            logging.warning(f"Не удалось проанализировать геомагнитную обстановку: {e}")

    # 5. Анализ Солнечной активности (Солнечный ветер)
    try:
        solar_wind = data.get('solar', {}).get('solar_wind_speed', [])
        if solar_wind:
            recent_avg = sum(solar_wind[-12:]) / 12 if len(solar_wind) >= 12 else 0
            historical_avg = sum(solar_wind) / len(solar_wind) if solar_wind else 0
            stats['solar_wind_recent'] = round(recent_avg, 1)
            stats['solar_wind_avg'] = round(historical_avg, 1)
            if historical_avg > 0 and recent_avg > historical_avg * 1.5:
                risks.append(("Низкий", "усиление солнечного ветра"))
    except Exception as e:
        logging.warning(f"Не удалось проанализировать солнечную активность: {e}")

    # 6. Анализ Качества воздуха (PM2.5, PM10, NO₂, O₃)
    if sensitivities['air_quality']:
        try:
            hourly_pm25 = air_hourly.get('pm2_5', [])
            hourly_pm10 = air_hourly.get('pm10', [])
            hourly_no2 = air_hourly.get('nitrogen_dioxide', [])
            hourly_o3 = air_hourly.get('ozone', [])
            hourly_times = air_times

            if hourly_pm25 and hourly_times:
                next_24h_pm25 = []
                next_24h_pm10 = []
                next_24h_no2 = []
                next_24h_o3 = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = parse_timezone_aware(t, user_tz)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_pm25): next_24h_pm25.append(hourly_pm25[i])
                            if i < len(hourly_pm10): next_24h_pm10.append(hourly_pm10[i])
                            if i < len(hourly_no2): next_24h_no2.append(hourly_no2[i])
                            if i < len(hourly_o3): next_24h_o3.append(hourly_o3[i])
                    except (ValueError, TypeError):
                        continue

                if next_24h_pm25:
                    avg_pm25 = sum(next_24h_pm25) / len(next_24h_pm25)
                    stats['pm25_avg'] = round(avg_pm25, 1)
                    if avg_pm25 > 35:
                        risks.append(("Высокий", f"высокий уровень PM2.5 (средний {round(avg_pm25, 1)} мкг/м³)"))
                    elif avg_pm25 > 15:
                        risks.append(("Средний", f"повышенный уровень PM2.5 (средний {round(avg_pm25, 1)} мкг/м³)"))
                    else:
                        stats['pm25_status'] = '✅ норма'

                if next_24h_pm10:
                    avg_pm10 = sum(next_24h_pm10) / len(next_24h_pm10)
                    stats['pm10_avg'] = round(avg_pm10, 1)
                    if avg_pm10 > 50:
                        risks.append(("Средний", f"высокий уровень PM10 (средний {round(avg_pm10, 1)} мкг/м³)"))
                    else:
                        stats['pm10_status'] = '✅ норма'

                if next_24h_o3:
                    avg_o3 = sum(next_24h_o3) / len(next_24h_o3)
                    stats['o3_avg'] = round(avg_o3, 1)
                    if avg_o3 > 100:
                        risks.append(("Средний", f"высокий уровень озона (средний {round(avg_o3, 1)} мкг/м³)"))
                    else:
                        stats['o3_status'] = '✅ норма'

                if next_24h_no2:
                    avg_no2 = sum(next_24h_no2) / len(next_24h_no2)
                    stats['no2_avg'] = round(avg_no2, 1)
                    if avg_no2 > 40:
                        risks.append(("Низкий", f"повышенный уровень NO₂ (средний {round(avg_no2, 1)} мкг/м³)"))
                    else:
                        stats['no2_status'] = '✅ норма'
        except Exception as e:
            logging.warning(f"Не удалось проанализировать качество воздуха: {e}")

    # 7. Анализ UV-индекса
    if sensitivities['uv']:
        try:
            hourly_uv = air_hourly.get('uv_index', [])
            hourly_times = air_times
            if hourly_uv and hourly_times:
                next_24h_uv = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = parse_timezone_aware(t, user_tz)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_uv):
                                next_24h_uv.append(hourly_uv[i])
                    except (ValueError, TypeError):
                        continue
                if next_24h_uv:
                    max_uv = max(next_24h_uv)
                    stats['uv_max'] = round(max_uv, 1)
                    if max_uv >= 8:
                        risks.append(("Высокий", f"очень высокий UV-индекс (до {round(max_uv, 1)})"))
                    elif max_uv >= 5:
                        risks.append(("Средний", f"высокий UV-индекс (до {round(max_uv, 1)})"))
                    elif max_uv >= 3:
                        risks.append(("Низкий", f"умеренный UV-индекс (до {round(max_uv, 1)})"))
                    else:
                        stats['uv_status'] = '✅ норма'
        except Exception as e:
            logging.warning(f"Не удалось проанализировать UV-индекс: {e}")

    # 8. Анализ Пыльцы (если у пользователя есть аллергены)
    if has_allergen_sensitivity:
        try:
            hourly_times = air_times
            pollen_map = {
                'alder': 'alder_pollen',
                'birch': 'birch_pollen',
                'grass': 'grass_pollen',
                'mugwort': 'mugwort_pollen',
                'olive': 'olive_pollen',
                'ragweed': 'ragweed_pollen',
            }
            pollen_names = {
                'alder': 'ольхи',
                'birch': 'берёзы',
                'grass': 'злаковых трав',
                'mugwort': 'полыни',
                'olive': 'оливы',
                'ragweed': 'амброзии',
            }

            for allergen_key, is_active in allergens.items():
                if not is_active:
                    continue
                api_key = pollen_map.get(allergen_key)
                if not api_key:
                    continue
                hourly_pollen = air_hourly.get(api_key, [])
                if not hourly_pollen:
                    continue

                next_24h_pollen = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = parse_timezone_aware(t, user_tz)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_pollen) and hourly_pollen[i] is not None:
                                next_24h_pollen.append(hourly_pollen[i])
                    except (ValueError, TypeError):
                        continue

                if next_24h_pollen:
                    max_pollen = max(next_24h_pollen)
                    stats[f'pollen_{allergen_key}'] = round(max_pollen, 1)
                    if max_pollen > 50:
                        risks.append(("Высокий", f"высокая концентрация пыльцы {pollen_names[allergen_key]} ({round(max_pollen)} grains/m³)"))
                    elif max_pollen > 20:
                        risks.append(("Средний", f"повышенная концентрация пыльцы {pollen_names[allergen_key]} ({round(max_pollen)} grains/m³)"))
                    elif max_pollen > 5:
                        risks.append(("Низкий", f"присутствует пыльца {pollen_names[allergen_key]} ({round(max_pollen)} grains/m³)"))
        except Exception as e:
            logging.warning(f"Не удалось проанализировать пыльцу: {e}")

    # 9. Анализ ощущаемой температуры
    if sensitivities['apparent_temperature']:
        try:
            hourly_temp = weather_hourly.get('temperature_2m', [])
            hourly_apparent = weather_hourly.get('apparent_temperature', [])
            hourly_times = weather_times
            if hourly_temp and hourly_apparent and hourly_times:
                next_24h_diffs = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = parse_timezone_aware(t, user_tz)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_temp) and i < len(hourly_apparent):
                                real = hourly_temp[i]
                                apparent = hourly_apparent[i]
                                if real is not None and apparent is not None:
                                    diff = abs(real - apparent)
                                    next_24h_diffs.append((diff, real, apparent))
                    except (ValueError, TypeError):
                        continue
                if next_24h_diffs:
                    max_diff, max_real, max_apparent = max(next_24h_diffs, key=lambda x: x[0])
                    stats['apparent_temp_diff_max'] = round(max_diff, 1)
                    stats['apparent_temp_real'] = round(max_real, 1)
                    stats['apparent_temp_feels'] = round(max_apparent, 1)
                    if max_diff > 8:
                        direction = "холоднее" if max_apparent < max_real else "теплее"
                        risks.append(("Высокий", f"большая разница между реальной и ощущаемой температурой (разница {round(max_diff)}°C, ощущается {direction})"))
                    elif max_diff > 5:
                        direction = "холоднее" if max_apparent < max_real else "теплее"
                        risks.append(("Средний", f"заметная разница между реальной и ощущаемой температурой (разница {round(max_diff)}°C, ощущается {direction})"))
                    else:
                        stats['apparent_temp_status'] = '✅ норма'
        except Exception as e:
            logging.warning(f"Не удалось проанализировать ощущаемую температуру: {e}")

    # 10. Анализ точки росы
    if sensitivities['dew_point']:
        try:
            hourly_dew = weather_hourly.get('dew_point_2m', [])
            hourly_times = weather_times
            if hourly_dew and hourly_times:
                next_24h_dew = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = parse_timezone_aware(t, user_tz)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_dew) and hourly_dew[i] is not None:
                                next_24h_dew.append(hourly_dew[i])
                    except (ValueError, TypeError):
                        continue
                if next_24h_dew:
                    max_dew = max(next_24h_dew)
                    min_dew = min(next_24h_dew)
                    stats['dew_point_max'] = round(max_dew, 1)
                    stats['dew_point_min'] = round(min_dew, 1)
                    if max_dew > 20:
                        risks.append(("Средний", f"очень высокая точка росы (до {round(max_dew)}°C) — душно, тяжёлый воздух"))
                    elif max_dew > 16:
                        risks.append(("Низкий", f"повышенная точка росы (до {round(max_dew)}°C) — ощущается духота"))
                    if min_dew < -15:
                        risks.append(("Низкий", f"очень низкая точка росы (до {round(min_dew)}°C) — сухой морозный воздух"))
                    if max_dew <= 20 and min_dew >= -15:
                        stats['dew_point_status'] = '✅ норма'
        except Exception as e:
            logging.warning(f"Не удалось проанализировать точку росы: {e}")

    # 11. Анализ видимости
    if sensitivities['visibility']:
        try:
            hourly_vis = weather_hourly.get('visibility', [])
            hourly_times = weather_times
            if hourly_vis and hourly_times:
                next_24h_vis = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = parse_timezone_aware(t, user_tz)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_vis) and hourly_vis[i] is not None:
                                next_24h_vis.append(hourly_vis[i])
                    except (ValueError, TypeError):
                        continue
                if next_24h_vis:
                    min_vis = min(next_24h_vis)
                    stats['visibility_min_km'] = round(min_vis / 1000, 1)
                    # visibility в метрах
                    if min_vis < 200:
                        risks.append(("Высокий", f"экстремально низкая видимость (до {round(min_vis / 1000, 1)} км) — туман/смог"))
                    elif min_vis < 1000:
                        risks.append(("Средний", f"низкая видимость (до {round(min_vis / 1000, 1)} км) — туман или задымление"))
                    elif min_vis < 5000:
                        risks.append(("Низкий", f"пониженная видимость (до {round(min_vis / 1000, 1)} км) — дымка или лёгкий туман"))
                    else:
                        stats['visibility_status'] = '✅ норма'
        except Exception as e:
            logging.warning(f"Не удалось проанализировать видимость: {e}")

    # 12. Анализ грозовой активности (CAPE)
    if sensitivities['storm']:
        try:
            hourly_cape = weather_hourly.get('cape', [])
            hourly_times = weather_times
            if hourly_cape and hourly_times:
                next_24h_cape = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = parse_timezone_aware(t, user_tz)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_cape) and hourly_cape[i] is not None:
                                next_24h_cape.append(hourly_cape[i])
                    except (ValueError, TypeError):
                        continue
                if next_24h_cape:
                    max_cape = max(next_24h_cape)
                    stats['cape_max'] = int(max_cape)
                    if max_cape > 2500:
                        risks.append(("Высокий", f"очень высокая конвективная энергия (CAPE до {int(max_cape)} J/kg) — вероятность грозы и мигреней"))
                    elif max_cape > 1000:
                        risks.append(("Средний", f"повышенная конвективная энергия (CAPE до {int(max_cape)} J/kg) — возможна гроза"))
                    elif max_cape > 500:
                        risks.append(("Низкий", f"умеренная конвективная энергия (CAPE до {int(max_cape)} J/kg)"))
                    else:
                        stats['cape_status'] = '✅ низкая'
        except Exception as e:
            logging.warning(f"Не удалось проанализировать грозовую активность: {e}")

    # 13. Анализ уровня замерзания
    if sensitivities['freezing_level']:
        try:
            hourly_fl = weather_hourly.get('freezing_level_height', [])
            hourly_times = weather_times
            if hourly_fl and hourly_times:
                next_24h_fl = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = parse_timezone_aware(t, user_tz)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_fl) and hourly_fl[i] is not None:
                                next_24h_fl.append(hourly_fl[i])
                    except (ValueError, TypeError):
                        continue
                if len(next_24h_fl) >= 2:
                    fl_change = abs(max(next_24h_fl) - min(next_24h_fl))
                    stats['freezing_level_change'] = int(fl_change)
                    if fl_change > 800:
                        risks.append(("Средний", f"резкое изменение уровня замерзания (на {int(fl_change)} м за сутки)"))
                    elif fl_change > 500:
                        risks.append(("Низкий", f"заметное изменение уровня замерзания (на {int(fl_change)} м за сутки)"))
                    else:
                        stats['freezing_level_status'] = '✅ стабильный'
        except Exception as e:
            logging.warning(f"Не удалось проанализировать уровень замерзания: {e}")

    return {"risks": risks, "stats": stats}


# --- Форматирование сообщений ---

def format_compact_message(analysis: dict) -> str:
    """
    Формирует компактное сообщение для рассылки по расписанию.
    """
    risks = analysis.get("risks", [])
    info_risks = [(l, r) for l, r in risks if l == "Инфо"]
    real_risks = [(l, r) for l, r in risks if l != "Инфо"]

    if not real_risks:
        msg = "Прогноз благоприятный. Никаких значительных метеофакторов, влияющих на самочувствие, не ожидается. ✨"
        if info_risks:
            msg += "\n\nℹ️ Дополнительно:\n"
            for _, reason in info_risks:
                msg += f"• {html.escape(reason)}\n"
        return msg

    risk_map = {"Высокий": 3, "Средний": 2, "Низкий": 1}
    real_risks.sort(key=lambda x: risk_map.get(x[0], 0), reverse=True)
    highest_risk_level = real_risks[0][0]

    if highest_risk_level == "Высокий":
        title = "РИСК ВЫСОКИЙ. Ожидаются значительные изменения в погоде. 😔"
    elif highest_risk_level == "Средний":
        title = "РИСК СРЕДНИЙ. Возможны изменения в самочувствии. 😟"
    else:
        title = "РИСК НЕБОЛЬШОЙ. Есть некоторые факторы, на которые стоит обратить внимание. 🤔"

    message = f"<b>{title}</b>\n\nВот что может повлиять на самочувствие:\n"
    for level, reason in real_risks:
        message += f"• <b>{level} риск:</b> {html.escape(reason)}\n"

    if info_risks:
        message += "\nℹ️ Дополнительно:\n"
        for _, reason in info_risks:
            message += f"• {html.escape(reason)}\n"

    return message


def format_detailed_message(analysis: dict) -> str:
    """
    Формирует развёрнутое сообщение с таблицей значений всех факторов.
    """
    risks = analysis.get("risks", [])
    stats = analysis.get("stats", {})

    # Заголовок — тот же что и в compact
    info_risks = [(l, r) for l, r in risks if l == "Инфо"]
    real_risks = [(l, r) for l, r in risks if l != "Инфо"]

    if not real_risks:
        title = "Прогноз благоприятный ✨"
    else:
        risk_map = {"Высокий": 3, "Средний": 2, "Низкий": 1}
        real_risks.sort(key=lambda x: risk_map.get(x[0], 0), reverse=True)
        highest = real_risks[0][0]
        if highest == "Высокий":
            title = "РИСК ВЫСОКИЙ 😔"
        elif highest == "Средний":
            title = "РИСК СРЕДНИЙ 😟"
        else:
            title = "РИСК НЕБОЛЬШОЙ 🤔"

    message = f"<b>{title}</b>\n\n"

    # Блок рисков (коротко)
    if real_risks:
        message += "<b>⚠️ Факторы риска:</b>\n"
        for level, reason in real_risks:
            emoji = {"Высокий": "🔴", "Средний": "🟡", "Низкий": "🟢"}.get(level, "⚪")
            message += f"{emoji} {html.escape(reason)}\n"
        message += "\n"

    # Таблица статистики — ВСЕ параметры
    message += "<b>📊 Подробные данные:</b>\n"

    def row(name, value):
        return f"• <b>{name}:</b> {html.escape(str(value))}\n"

    # --- ДАВЛЕНИЕ ---
    if "pressure_min" in stats:
        status = stats.get('pressure_status', '')
        message += row("Давление", f"{stats['pressure_min']}–{stats['pressure_max']} мм рт. ст. (Δ {stats['pressure_change_24h']} за 24ч){status}")
    if "pressure_rate" in stats:
        status = stats.get('pressure_rate_status', '')
        message += row("Скорость давления", f"{stats['pressure_rate']} мм рт. ст./ч{status}")
    if "pressure_peak_time" in stats:
        message += row("Пик давления", f"~{stats['pressure_peak_time']}")

    # --- ТЕМПЕРАТУРА ---
    if "temp_today_max" in stats:
        status = stats.get('temp_status', '')
        message += row("Температура", f"сегодня {stats['temp_today_max']}°C / вчера {stats['temp_yesterday_max']}°C (Δ {stats['temp_diff']}°C){status}")
    if "temp_rate" in stats:
        status = stats.get('temp_rate_status', '')
        message += row("Скорость температуры", f"{stats['temp_rate']}°C/ч{status}")

    # --- ВЛАЖНОСТЬ ---
    if "humidity_avg" in stats:
        h = stats['humidity_avg']
        badge = stats.get('humidity_status', '')
        if not badge:
            if h > 85: badge = "🟡 высокая"
            elif h < 30: badge = "🟡 низкая"
            else: badge = "✅ норма"
        message += row("Влажность", f"{h}% {badge}")

    # --- ГЕОМАГНИТНАЯ АКТИВНОСТЬ ---
    if "kp_max" in stats:
        k = stats['kp_max']
        badge = stats.get('kp_status', '')
        if not badge:
            if k >= 5: badge = "🔴 буря"
            elif k >= 3: badge = "🟡 повышена"
            else: badge = "✅ норма"
        message += row("Kp-индекс", f"{k} {badge}")

    # --- СОЛНЕЧНЫЙ ВЕТЕР ---
    if "solar_wind_recent" in stats:
        msg_sw = f"{stats['solar_wind_recent']} км/с"
        if stats['solar_wind_recent'] > stats['solar_wind_avg'] * 1.5:
            msg_sw += " 🟡 усилен"
        else:
            msg_sw += " ✅ норма"
        message += row("Солнечный ветер", msg_sw)

    # --- КАЧЕСТВО ВОЗДУХА ---
    if "pm25_avg" in stats:
        p = stats['pm25_avg']
        badge = stats.get('pm25_status', '')
        if not badge:
            if p > 35: badge = "🔴 высокий"
            elif p > 15: badge = "🟡 повышен"
            else: badge = "✅ норма"
        message += row("PM2.5", f"{p} мкг/м³ {badge}")

    if "pm10_avg" in stats:
        p = stats['pm10_avg']
        badge = stats.get('pm10_status', '')
        if not badge:
            if p > 50: badge = "🟡 высокий"
            else: badge = "✅ норма"
        message += row("PM10", f"{p} мкг/м³ {badge}")

    if "o3_avg" in stats:
        o = stats['o3_avg']
        badge = stats.get('o3_status', '')
        if not badge:
            if o > 100: badge = "🟡 высокий"
            else: badge = "✅ норма"
        message += row("Озон O₃", f"{o} мкг/м³ {badge}")

    if "no2_avg" in stats:
        n = stats['no2_avg']
        badge = stats.get('no2_status', '')
        if not badge:
            if n > 40: badge = "🟡 повышен"
            else: badge = "✅ норма"
        message += row("NO₂", f"{n} мкг/м³ {badge}")

    # --- UV-ИНДЕКС ---
    if "uv_max" in stats:
        u = stats['uv_max']
        badge = stats.get('uv_status', '')
        if not badge:
            if u >= 8: badge = "🔴 очень высокий"
            elif u >= 5: badge = "🟡 высокий"
            elif u >= 3: badge = "🟢 умеренный"
            else: badge = "✅ низкий"
        message += row("UV-индекс", f"{u} {badge}")

    # --- ОЩУЩАЕМАЯ ТЕМПЕРАТУРА ---
    if "apparent_temp_diff_max" in stats:
        d = stats['apparent_temp_diff_max']
        badge = "🔴 большая" if d > 8 else "🟡 заметная" if d > 5 else "✅ норма"
        message += row("Ощущаемая t°", f"{stats['apparent_temp_real']}°C → ощущается {stats['apparent_temp_feels']}°C (разница {d}°C) {badge}")

    # --- ТОЧКА РОСЫ ---
    if "dew_point_max" in stats:
        dp_max = stats['dew_point_max']
        dp_min = stats['dew_point_min']
        badge = ""
        if dp_max > 20: badge = "🟡 душно"
        elif dp_max > 16: badge = "🟢 лёгкая духота"
        if dp_min < -15: badge += " 🟢 сухо"
        if not badge: badge = "✅ норма"
        message += row("Точка росы", f"от {dp_min}°C до {dp_max}°C{badge}")

    # --- ВИДИМОСТЬ ---
    if "visibility_min_km" in stats:
        v = stats['visibility_min_km']
        badge = ""
        if v < 0.2: badge = "🔴 экстремально низкая"
        elif v < 1: badge = "🟡 низкая"
        elif v < 5: badge = "🟢 пониженная"
        else: badge = "✅ норма"
        message += row("Видимость", f"от {v} км {badge}")

    # --- ГРОЗОВАЯ АКТИВНОСТЬ (CAPE) ---
    if "cape_max" in stats:
        c = stats['cape_max']
        badge = ""
        if c > 2500: badge = "🔴 очень высокая"
        elif c > 1000: badge = "🟡 повышенная"
        elif c > 500: badge = "🟢 умеренная"
        else: badge = "✅ низкая"
        message += row("CAPE (гроза)", f"{c} J/kg {badge}")

    # --- УРОВЕНЬ ЗАМЕРЗАНИЯ ---
    if "freezing_level_change" in stats:
        fl = stats['freezing_level_change']
        badge = ""
        if fl > 800: badge = "🟡 резкое"
        elif fl > 500: badge = "🟢 заметное"
        else: badge = "✅ стабильный"
        message += row("Уровень замерзания", f"изменение {fl} м {badge}")

    # --- ПЫЛЬЦА (если есть) ---
    pollen_keys = [k for k in stats if k.startswith('pollen_')]
    if pollen_keys:
        message += "\n<b>🌿 Пыльца:</b>\n"
        pollen_names_ru = {
            'pollen_alder': 'ольха', 'pollen_birch': 'берёза',
            'pollen_grass': 'злаковые', 'pollen_mugwort': 'полынь',
            'pollen_olive': 'олива', 'pollen_ragweed': 'амброзия',
        }
        for pk in pollen_keys:
            val = stats[pk]
            name = pollen_names_ru.get(pk, pk)
            badge = "🔴 высокая" if val > 50 else "🟡 повышенная" if val > 20 else "🟢 присутствует" if val > 5 else "✅ низкая"
            message += f"• <b>{name}:</b> {val} grains/m³ {badge}\n"

    message += "\n/info — подробнее о каждом факторе."
    return message
