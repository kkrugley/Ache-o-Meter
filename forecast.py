import logging
import aiohttp
from datetime import datetime, timedelta
import asyncio
import html

# --- Сбор данных с API ---

async def get_forecast_data(lat: float, lon: float):
    """
    Асинхронно собирает все необходимые данные о погоде, пыльце и магнитных бурях.
    """
    # Используем asyncio.gather для параллельного выполнения запросов
    weather_data, geo_data = await asyncio.gather(
        get_open_meteo_data(lat, lon),
        get_noaa_geo_data()
    )
    # Объединяем результаты в один словарь
    return {**weather_data, **geo_data}

async def get_open_meteo_data(lat: float, lon: float):
    """
    Получает прогноз погоды и данные о пыльце с Open-Meteo.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'temperature_2m,surface_pressure',
        'daily': 'temperature_2m_max,temperature_2m_min',
        'forecast_days': 2,  # Запрашиваем данные на 48 часов
        'timezone': 'auto',
        # ИСПРАВЛЕНО: Используем правильный параметр для данных о пыльце
        'pollen': 'birch_pollen,grass_pollen,ragweed_pollen'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()  # Проверяем на HTTP ошибки
                logging.info("Данные с Open-Meteo успешно получены.")
                return await response.json()
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка при запросе к Open-Meteo: {e}")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при получении данных с Open-Meteo: {e}")
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
                # Преобразуем данные в удобный формат, пропуская заголовок
                processed_data = [
                    {'time_tag': item[0], 'kp_value': float(item[1]), 'observation_status': item[2]}
                    for item in data[1:] if len(item) >= 3
                ]
                logging.info("Данные о геомагнитной обстановке с NOAA успешно получены.")
                return {'geo_forecast': processed_data}
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка при запросе к NOAA: {e}")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при получении данных с NOAA: {e}")
    return {}

# --- Анализ и формирование сообщения ---

def analyze_data_and_form_message(data: dict):
    """
    Анализирует собранные данные и формирует итоговое сообщение для пользователя.
    """
    if not data:
        return "Не удалось получить данные для прогноза. Попробуем позже. 🤷‍♂️"

    reasons = []  # Список причин для плохого самочувствия

    # 1. УЛУЧШЕННЫЙ АНАЛИЗ ПЕРЕПАДА ДАВЛЕНИЯ
    try:
        # Берем данные за ближайшие 24 часа
        hourly_pressure = data['hourly']['surface_pressure'][:24]
        if hourly_pressure:
            min_pressure = min(hourly_pressure)
            max_pressure = max(hourly_pressure)
            pressure_diff = abs(max_pressure - min_pressure)
            # Порог в 8 гПа считается значительным
            if pressure_diff > 8:
                reasons.append(f"резкий перепад давления (на {round(pressure_diff)} гПа в течение суток)")
    except (KeyError, IndexError, TypeError) as e:
        logging.warning(f"Не удалось проанализировать давление: {e}")

    # 2. УЛУЧШЕННЫЙ АНАЛИЗ ГЕОМАГНИТНОЙ ОБСТАНОВКИ (Kp-индекс)
    try:
        geo_forecast = data.get('geo_forecast', [])
        now_utc = datetime.utcnow()
        # Проверяем прогноз на 24 часа вперед
        future_limit = now_utc + timedelta(hours=24)
        
        max_kp = 0
        for forecast in geo_forecast:
            # Преобразуем строку времени в datetime объект
            forecast_time = datetime.fromisoformat(forecast['time_tag'].replace('Z', '+00:00'))
            if now_utc <= forecast_time < future_limit:
                if forecast['kp_value'] > max_kp:
                    max_kp = forecast['kp_value']
        
        if max_kp >= 5:
            reasons.append(f"ожидается магнитная буря (Kp-индекс до {int(max_kp)})")
    except Exception as e:
        logging.warning(f"Не удалось проанализировать геомагнитную обстановку: {e}")

    # 3. ИСПРАВЛЕННЫЙ АНАЛИЗ ПЫЛЬЦЫ
    try:
        if 'pollen' in data:
            pollen_data = data['pollen']
            pollen_types = []
            # Проверяем каждый тип пыльцы на ближайшие 24 часа
            if any(p > 15 for p in pollen_data.get('birch_pollen', [])[:24] if p is not None):
                pollen_types.append("берёзы")
            if any(p > 15 for p in pollen_data.get('grass_pollen', [])[:24] if p is not None):
                pollen_types.append("злаковых трав")
            if any(p > 15 for p in pollen_data.get('ragweed_pollen', [])[:24] if p is not None):
                pollen_types.append("амброзии")
            
            if pollen_types:
                reasons.append(f"высокий уровень пыльцы в воздухе ({', '.join(pollen_types)})")
    except (KeyError, IndexError, TypeError) as e:
        logging.warning(f"Не удалось проанализировать данные по пыльце: {e}")

    # --- Формирование итогового сообщения ---
    if not reasons:
        # Добавим немного динамики в позитивные сообщения
        from random import choice
        positive_messages = [
            "Сегодня всё спокойно, живи-балдей! 😎",
            "Прогноз благоприятный. Можно сворачивать горы! ⛰️",
            "Никаких угроз для самочувствия не найдено. Наслаждайся днём! ✨"
        ]
        return choice(positive_messages)
    
    if len(reasons) == 1:
        return f"Oof! Кажется, сегодня стоит поберечь себя из-за <b>{html.escape(reasons[0])}</b>. Держись, друг! 😔"

    message = "Oof! Кажется, сегодня комбо. Держись, друг! 😔<br><br>Вот что может повлиять на самочувствие:<br>"
    for reason in reasons:
        message += f"• {html.escape(reason.capitalize())}<br>"
        
    return message
