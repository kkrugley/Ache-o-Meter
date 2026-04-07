import logging
import aiohttp
from datetime import datetime, timedelta
import asyncio
import html
import pytz

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
}

async def get_forecast_data(lat: float, lon: float):
    """
    Асинхронно собирает все необходимые данные о погоде, геомагнитной и солнечной активности,
    качестве воздуха и пыльце.
    """
    weather_data, geo_data, solar_data, air_data = await asyncio.gather(
        get_open_meteo_data(lat, lon),
        get_noaa_geo_data(),
        get_solar_activity_data(),
        get_air_quality_data(lat, lon),
    )
    return {**weather_data, **geo_data, **solar_data, **air_data}


async def get_open_meteo_data(lat: float, lon: float):
    """
    Получает прогноз погоды (температура, давление, влажность) с Open-Meteo.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'temperature_2m,surface_pressure,relative_humidity_2m',
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
    return {}


# --- Анализ и формирование сообщения ---

def analyze_data_and_form_message(data: dict, user_profile: dict = None):
    """
    Анализирует собранные данные и формирует итоговое сообщение.
    Учитывает профиль пользователя (чувствительность, аллергены).
    """
    if not data:
        return "Не удалось получить данные для прогноза. Попробуем позже. 🤷‍♂️"

    # Определяем, какие факторы учитывать
    sensitivities = {
        'pressure': True,
        'temperature': True,
        'humidity': True,
        'geomagnetic': True,
        'air_quality': True,
        'uv': True,
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

    risks = []
    now = datetime.now().astimezone()

    has_allergen_sensitivity = any(allergens.values())

    # 1. Анализ Атмосферного давления
    if sensitivities['pressure']:
        try:
            hourly_pressure = data.get('hourly', {}).get('surface_pressure', [])
            hourly_times = data.get('hourly', {}).get('time', [])
            if hourly_pressure and hourly_times:
                past_24h = []
                future_24h = []
                for t, p in zip(hourly_times, hourly_pressure):
                    try:
                        dt = datetime.fromisoformat(t)
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

                    if abs(pressure_change_24h) > 7:
                        risks.append(("Высокий", f"очень резкий перепад давления (изменение на {round(pressure_change_24h)} мм рт. ст. за сутки)"))
                    elif abs(pressure_change_24h) > 3:
                        risks.append(("Средний", f"заметный перепад давления (изменение на {round(pressure_change_24h)} мм рт. ст. за сутки)"))

                    # Скорость изменения давления (мм рт. ст./час)
                    if len(past_24h) >= 2:
                        sorted_past = sorted(past_24h, key=lambda x: x[0])
                        time_span_hours = (sorted_past[-1][0] - sorted_past[0][0]).total_seconds() / 3600
                        if time_span_hours > 0:
                            pressure_rate = abs(sorted_past[-1][1] - sorted_past[0][1]) * hpa_to_mmhg / time_span_hours
                            if pressure_rate > 1.0:
                                risks.append(("Средний", f"быстрое изменение давления ({round(pressure_rate, 1)} мм рт. ст./час)"))

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
                            risks.append(("Инфо", f"пиковый час по давлению: ~{peak_time_str}"))
        except (KeyError, IndexError, TypeError) as e:
            logging.warning(f"Не удалось проанализировать давление: {e}")

    # 2. Анализ Температурных колебаний
    if sensitivities['temperature']:
        try:
            daily_temp = data.get('daily', {})
            if daily_temp.get('temperature_2m_max'):
                today_max = daily_temp['temperature_2m_max'][1] if len(daily_temp['temperature_2m_max']) > 1 else daily_temp['temperature_2m_max'][0]
                yesterday_max = daily_temp['temperature_2m_max'][0]
                temp_diff = abs(today_max - yesterday_max)

                if temp_diff > 10:
                    risks.append(("Высокий", f"очень резкое изменение температуры (на {round(temp_diff)}°C по сравнению со вчерашним днём)"))
                elif temp_diff > 5:
                    risks.append(("Средний", f"заметное изменение температуры (на {round(temp_diff)}°C по сравнению со вчерашним днём)"))

                # Скорость изменения температуры
                hourly_temp = data.get('hourly', {}).get('temperature_2m', [])
                hourly_times = data.get('hourly', {}).get('time', [])
                if hourly_temp and hourly_times and len(hourly_temp) >= 2:
                    recent = []
                    for t, temp in zip(hourly_times, hourly_temp):
                        try:
                            dt = datetime.fromisoformat(t)
                            if now - timedelta(hours=6) <= dt <= now:
                                recent.append((dt, temp))
                        except (ValueError, TypeError):
                            continue
                    if len(recent) >= 2:
                        sorted_recent = sorted(recent, key=lambda x: x[0])
                        time_span = (sorted_recent[-1][0] - sorted_recent[0][0]).total_seconds() / 3600
                        if time_span > 0:
                            temp_rate = abs(sorted_recent[-1][1] - sorted_recent[0][1]) / time_span
                            if temp_rate > 2.0:
                                risks.append(("Средний", f"быстрое изменение температуры ({round(temp_rate, 1)}°C/час)"))
        except (KeyError, IndexError, TypeError) as e:
            logging.warning(f"Не удалось проанализировать температуру: {e}")

    # 3. Анализ Влажности
    if sensitivities['humidity']:
        try:
            hourly_humidity = data.get('hourly', {}).get('relative_humidity_2m', [])
            hourly_times = data.get('hourly', {}).get('time', [])
            if hourly_humidity and hourly_times:
                past_24h_humidity = []
                for t, h in zip(hourly_times, hourly_humidity):
                    try:
                        dt = datetime.fromisoformat(t)
                        if now - timedelta(hours=24) <= dt < now:
                            past_24h_humidity.append(h)
                    except (ValueError, TypeError):
                        continue
                if past_24h_humidity:
                    avg_humidity = sum(past_24h_humidity) / len(past_24h_humidity)
                    if avg_humidity > 85:
                        risks.append(("Низкий", "очень высокая влажность воздуха"))
                    elif avg_humidity < 30:
                        risks.append(("Низкий", "очень низкая влажность воздуха"))
        except (KeyError, IndexError, TypeError) as e:
            logging.warning(f"Не удалось проанализировать влажность: {e}")

    # 4. Анализ Геомагнитной активности (Kp-индекс)
    if sensitivities['geomagnetic']:
        try:
            geo_forecast = data.get('geo_forecast', [])
            future_limit = datetime.utcnow().replace(tzinfo=pytz.UTC) + timedelta(hours=24)
            max_kp = 0
            for forecast in geo_forecast:
                forecast_time = datetime.fromisoformat(forecast['time_tag'].replace('Z', '+00:00'))
                if forecast_time < future_limit and forecast['kp_value'] > max_kp:
                    max_kp = forecast['kp_value']

            if max_kp >= 5:
                risks.append(("Высокий", f"ожидается магнитная буря (Kp-индекс до {int(max_kp)})"))
            elif max_kp >= 3:
                risks.append(("Средний", f"повышенная геомагнитная активность (Kp-индекс до {int(max_kp)})"))
        except Exception as e:
            logging.warning(f"Не удалось проанализировать геомагнитную обстановку: {e}")

    # 5. Анализ Солнечной активности (Солнечный ветер)
    try:
        solar_wind = data.get('solar_wind_speed', [])
        if solar_wind:
            recent_avg = sum(solar_wind[-12:]) / 12 if len(solar_wind) >= 12 else 0
            historical_avg = sum(solar_wind) / len(solar_wind) if solar_wind else 0
            if historical_avg > 0 and recent_avg > historical_avg * 1.5:
                risks.append(("Низкий", "усиление солнечного ветра"))
    except Exception as e:
        logging.warning(f"Не удалось проанализировать солнечную активность: {e}")

    # 6. Анализ Качества воздуха (PM2.5, PM10, NO₂, O₃)
    if sensitivities['air_quality']:
        try:
            hourly_pm25 = data.get('hourly', {}).get('pm2_5', [])
            hourly_pm10 = data.get('hourly', {}).get('pm10', [])
            hourly_no2 = data.get('hourly', {}).get('nitrogen_dioxide', [])
            hourly_o3 = data.get('hourly', {}).get('ozone', [])
            hourly_times = data.get('hourly', {}).get('time', [])

            if hourly_pm25 and hourly_times:
                next_24h_pm25 = []
                next_24h_pm10 = []
                next_24h_no2 = []
                next_24h_o3 = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = datetime.fromisoformat(t)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_pm25): next_24h_pm25.append(hourly_pm25[i])
                            if i < len(hourly_pm10): next_24h_pm10.append(hourly_pm10[i])
                            if i < len(hourly_no2): next_24h_no2.append(hourly_no2[i])
                            if i < len(hourly_o3): next_24h_o3.append(hourly_o3[i])
                    except (ValueError, TypeError):
                        continue

                if next_24h_pm25:
                    avg_pm25 = sum(next_24h_pm25) / len(next_24h_pm25)
                    if avg_pm25 > 35:
                        risks.append(("Высокий", f"высокий уровень PM2.5 (средний {round(avg_pm25, 1)} мкг/м³)"))
                    elif avg_pm25 > 15:
                        risks.append(("Средний", f"повышенный уровень PM2.5 (средний {round(avg_pm25, 1)} мкг/м³)"))

                if next_24h_pm10:
                    avg_pm10 = sum(next_24h_pm10) / len(next_24h_pm10)
                    if avg_pm10 > 50:
                        risks.append(("Средний", f"высокий уровень PM10 (средний {round(avg_pm10, 1)} мкг/м³)"))

                if next_24h_o3:
                    avg_o3 = sum(next_24h_o3) / len(next_24h_o3)
                    if avg_o3 > 100:
                        risks.append(("Средний", f"высокий уровень озона (средний {round(avg_o3, 1)} мкг/м³)"))

                if next_24h_no2:
                    avg_no2 = sum(next_24h_no2) / len(next_24h_no2)
                    if avg_no2 > 40:
                        risks.append(("Низкий", f"повышенный уровень NO₂ (средний {round(avg_no2, 1)} мкг/м³)"))
        except Exception as e:
            logging.warning(f"Не удалось проанализировать качество воздуха: {e}")

    # 7. Анализ UV-индекса
    if sensitivities['uv']:
        try:
            hourly_uv = data.get('hourly', {}).get('uv_index', [])
            hourly_times = data.get('hourly', {}).get('time', [])
            if hourly_uv and hourly_times:
                next_24h_uv = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = datetime.fromisoformat(t)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_uv):
                                next_24h_uv.append(hourly_uv[i])
                    except (ValueError, TypeError):
                        continue
                if next_24h_uv:
                    max_uv = max(next_24h_uv)
                    if max_uv >= 8:
                        risks.append(("Высокий", f"очень высокий UV-индекс (до {round(max_uv, 1)})"))
                    elif max_uv >= 5:
                        risks.append(("Средний", f"высокий UV-индекс (до {round(max_uv, 1)})"))
                    elif max_uv >= 3:
                        risks.append(("Низкий", f"умеренный UV-индекс (до {round(max_uv, 1)})"))
        except Exception as e:
            logging.warning(f"Не удалось проанализировать UV-индекс: {e}")

    # 8. Анализ Пыльцы (если у пользователя есть аллергены)
    if has_allergen_sensitivity:
        try:
            hourly_times = data.get('hourly', {}).get('time', [])
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
                hourly_pollen = data.get('hourly', {}).get(api_key, [])
                if not hourly_pollen:
                    continue

                next_24h_pollen = []
                for i, t in enumerate(hourly_times):
                    try:
                        dt = datetime.fromisoformat(t)
                        if now <= dt < now + timedelta(hours=24):
                            if i < len(hourly_pollen) and hourly_pollen[i] is not None:
                                next_24h_pollen.append(hourly_pollen[i])
                    except (ValueError, TypeError):
                        continue

                if next_24h_pollen:
                    max_pollen = max(next_24h_pollen)
                    if max_pollen > 50:
                        risks.append(("Высокий", f"высокая концентрация пыльцы {pollen_names[allergen_key]} ({round(max_pollen)} grains/m³)"))
                    elif max_pollen > 20:
                        risks.append(("Средний", f"повышенная концентрация пыльцы {pollen_names[allergen_key]} ({round(max_pollen)} grains/m³)"))
                    elif max_pollen > 5:
                        risks.append(("Низкий", f"присутствует пыльца {pollen_names[allergen_key]} ({round(max_pollen)} grains/m³)"))
        except Exception as e:
            logging.warning(f"Не удалось проанализировать пыльцу: {e}")

    # --- Формирование итогового сообщения ---
    # Убираем информационные записи из сортировки
    info_risks = [(l, r) for l, r in risks if l == "Инфо"]
    real_risks = [(l, r) for l, r in risks if l != "Инфо"]

    if not real_risks:
        msg = "Прогноз благоприятный. Никаких значительных метеофакторов, влияющих на самочувствие, не ожидается. ✨"
        if info_risks:
            msg += "\n\nℹ️ Дополнительно:\n"
            for _, reason in info_risks:
                msg += f"• {html.escape(reason)}\n"
        return msg

    # Сортируем риски по уровню
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

    message += "\nЧтобы узнать подробнее о каждом факторе, используй команду /info."
    return message
