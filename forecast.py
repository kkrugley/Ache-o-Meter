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
    "solar_activity": "<b>☀️ Солнечная активность:</b> Усиление солечного ветра может косвенно влиять на геомагнитную обстановку Земли и, как следствие, на самочувствие."
}

async def get_forecast_data(lat: float, lon: float):
    """
    Асинхронно собирает все необходимые данные о погоде, геомагнитной и солнечной активности.
    """
    weather_data, geo_data, solar_data = await asyncio.gather(
        get_open_meteo_data(lat, lon),
        get_noaa_geo_data(),
        get_solar_activity_data()
    )
    return {**weather_data, **geo_data, **solar_data}

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
                    {'time_tag': item[0], 'kp_value': float(item[1]), 'observation_status': item[2]}
                    for item in data[1:] if len(item) >= 3
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
    # Данные обновляются с задержкой, берем данные за последние 3 дня для анализа
    start_date = (datetime.utcnow() - timedelta(days=3)).strftime('%Y-%m-%d')
    end_date = datetime.utcnow().strftime('%Y-%m-%d')
    url = f"https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                # Пропускаем заголовок и берем только скорость
                processed_data = [float(item[1]) for item in data[1:] if len(item) > 1 and item[1] != '-9999.9']
                logging.info("Данные о солнечной активности успешно получены.")
                return {'solar_wind_speed': processed_data}
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка при запросе к NOAA (solar wind): {e}")
    return {}


# --- Анализ и формирование сообщения ---

def analyze_data_and_form_message(data: dict):
    """
    Анализирует собранные данные в соответствии с новыми требованиями и формирует итоговое сообщение.
    """
    if not data:
        return "Не удалось получить данные для прогноза. Попробуем позже. 🤷‍♂️"

    risks = []
    now = datetime.now().astimezone()
    
    # 1. Анализ Атмосферного давления
    try:
        hourly_pressure = data['hourly']['surface_pressure']
        # Данные за последние 24 часа и прогноз на 24 часа
        past_24h_pressure = [p for t, p in zip(data['hourly']['time'], hourly_pressure) if now - timedelta(hours=24) <= datetime.fromisoformat(t) < now]
        future_24h_pressure = [p for t, p in zip(data['hourly']['time'], hourly_pressure) if now <= datetime.fromisoformat(t) < now + timedelta(hours=24)]
        
        if past_24h_pressure and future_24h_pressure:
            # Перевод из гПа в мм рт. ст. (1 гПа ≈ 0.750062 мм рт. ст.)
            hpa_to_mmhg = 0.750062
            pressure_change_24h = (max(future_24h_pressure) - min(past_24h_pressure)) * hpa_to_mmhg
            
            if abs(pressure_change_24h) > 7:
                risks.append(("Высокий", f"очень резкий перепад давления (изменение на {round(pressure_change_24h)} мм рт. ст. за сутки)"))
            elif abs(pressure_change_24h) > 3:
                risks.append(("Средний", f"заметный перепад давления (изменение на {round(pressure_change_24h)} мм рт. ст. за сутки)"))

    except (KeyError, IndexError, TypeError) as e:
        logging.warning(f"Не удалось проанализировать давление: {e}")

    # 2. Анализ Температурных колебаний
    try:
        daily_temp = data['daily']
        today_max = daily_temp['temperature_2m_max'][1]
        yesterday_max = daily_temp['temperature_2m_max'][0]
        temp_diff = abs(today_max - yesterday_max)

        if temp_diff > 10:
            risks.append(("Высокий", f"очень резкое изменение температуры (на {round(temp_diff)}°C по сравнению со вчерашним днём)"))
        elif temp_diff > 5:
            risks.append(("Средний", f"заметное изменение температуры (на {round(temp_diff)}°C по сравнению со вчерашним днём)"))
            
    except (KeyError, IndexError, TypeError) as e:
        logging.warning(f"Не удалось проанализировать температуру: {e}")

    # 3. Анализ Влажности
    try:
        hourly_humidity = data['hourly']['relative_humidity_2m']
        # Данные за последние 24 часа
        past_24h_humidity = [h for t, h in zip(data['hourly']['time'], hourly_humidity) if now - timedelta(hours=24) <= datetime.fromisoformat(t) < now]
        if past_24h_humidity:
            avg_humidity = sum(past_24h_humidity) / len(past_24h_humidity)
            if avg_humidity > 85:
                risks.append(("Низкий", "очень высокая влажность воздуха"))
            elif avg_humidity < 30:
                risks.append(("Низкий", "очень низкая влажность воздуха"))

    except (KeyError, IndexError, TypeError) as e:
        logging.warning(f"Не удалось проанализировать влажность: {e}")

    # 4. Анализ Геомагнитной активности (Kp-индекс)
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
            # Сравниваем среднее за последний час с среднем за последние 3 дня
            recent_avg = sum(solar_wind[-12:]) / 12 if len(solar_wind) >= 12 else 0
            historical_avg = sum(solar_wind) / len(solar_wind)
            if recent_avg > historical_avg * 1.5: # Если скорость выросла в 1.5 раза
                 risks.append(("Низкий", "усиление солнечного ветра"))

    except Exception as e:
        logging.warning(f"Не удалось проанализировать солнечную активность: {e}")


    # --- Формирование итогового сообщения ---
    if not risks:
        return "Прогноз благоприятный. Никаких значительных метеофакторов, влияющих на самочувствие, не ожидается. ✨"

    # Сортируем риски по уровню: Высокий -> Средний -> Низкий
    risk_map = {"Высокий": 2, "Средний": 1, "Низкий": 0}
    risks.sort(key=lambda x: risk_map[x[0]], reverse=True)
    
    highest_risk_level = risks[0][0]
    
    if highest_risk_level == "Высокий":
        title = "РИСК ВЫСОКИЙ. Ожидаются значительные изменения в погоде. 😔"
    elif highest_risk_level == "Средний":
        title = "РИСК СРЕДНИЙ. Возможны изменения в самочувствии. 😟"
    else: # Низкий
        title = "РИСК НЕБОЛЬШОЙ. Есть некоторые факторы, на которые стоит обратить внимание. 🤔"

    message = f"<b>{title}</b>\n\nВот что может повлиять на самочувствие:\n"
    for level, reason in risks:
        message += f"• <b>{level} риск:</b> {html.escape(reason)}\n"
        
    message += "\nЧтобы узнать подробнее о каждом факторе, используй команду /info."
    return message