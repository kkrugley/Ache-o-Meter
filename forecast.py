import logging
import aiohttp
from datetime import datetime, timedelta
import asyncio


async def get_forecast_data(lat: float, lon: float):
    """
    Получает данные о погоде, пыльце и магнитных бурях.
    """
    # Собираем все данные асинхронно
    weather_data, geo_data = await asyncio.gather(
        get_open_meteo_data(lat, lon),
        get_noaa_geo_data()
    )
    return {**weather_data, **geo_data}

async def get_open_meteo_data(lat: float, lon: float):
    """Получает погоду и данные о пыльце с Open-Meteo."""
    url = "https://api.open-meteo.com/v1/forecast"
    # Запрашиваем данные на сегодня и на завтра
    params = {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'temperature_2m,surface_pressure',
        'daily': 'temperature_2m_max,temperature_2m_min',
        'forecast_days': 2,
        'timezone': 'auto',
        # Добавляем данные по пыльце
        'european_aqi': 'pollen_birch,pollen_grass,pollen_ragweed'
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    logging.info("Данные с Open-Meteo успешно получены.")
                    return await response.json()
    except Exception as e:
        logging.error(f"Ошибка при получении данных с Open-Meteo: {e}")
    return {}

async def get_noaa_geo_data():
    """Получает прогноз геомагнитной активности (Kp-индекс) с NOAA."""
    # NOAA обновляет этот файл каждые 3 часа
    url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # Преобразуем данные в удобный формат
                    # [[время, кп-индекс, статус], ...]
                    processed_data = []
                    for item in data[1:]: # Пропускаем заголовок
                        # Проверяем, что в записи есть все три элемента
                        if len(item) >= 3:
                            processed_data.append({
                                'time': item[0],
                                'kp': float(item[1]),
                                'status': item[2]
                            })
                    logging.info("Данные о геомагнитной обстановке с NOAA успешно получены.")
                    return {'geo_forecast': processed_data}
    except Exception as e:
        logging.error(f"Ошибка при получении данных с NOAA: {e}")
    return {}

# --- Анализ и формирование сообщения ---

def analyze_data_and_form_message(data: dict):
    """
    Анализирует собранные данные и формирует итоговое сообщение для пользователя.
    """
    if not data:
        return "Не удалось получить данные для прогноза. Попробуем позже. 🤷‍♂️"

    reasons = [] # Список причин для плохого самочувствия

    # 1. Анализ перепада давления
    try:
        hourly_pressure = data['hourly']['surface_pressure']
        # Ищем давление на 8 утра сегодня и завтра
        pressure_today = hourly_pressure[8]
        pressure_tomorrow = hourly_pressure[32] # 24+8
        pressure_diff = abs(pressure_today - pressure_tomorrow)
        if pressure_diff > 8: # Перепад более 8 гПа считается значительным
            reasons.append(f"Резкий перепад давления (около {round(pressure_diff)} гПа)")
    except (KeyError, IndexError):
        logging.warning("Не удалось проанализировать давление.")

    # 2. Анализ геомагнитной обстановки (Kp-индекс)
    try:
        geo_forecast = data.get('geo_forecast', [])
        # Ищем максимальный Kp-индекс на сегодня
        max_kp = 0
        today_str = (datetime.utcnow()).strftime('%Y-%m-%d')
        for forecast in geo_forecast:
            if forecast['time'].startswith(today_str):
                if forecast['kp'] > max_kp:
                    max_kp = forecast['kp']
        
        if max_kp >= 5:
            reasons.append(f"Ожидается магнитная буря (Kp-индекс до {int(max_kp)})")
    except Exception as e:
        logging.warning(f"Не удалось проанализировать геомагнитную обстановку: {e}")
        
    # 3. Анализ пыльцы (в API Open-Meteo нет общего индекса, смотрим по видам)
    try:
        # Для простоты просто проверим, есть ли вообще блок с пыльцой
        if 'european_aqi' in data and data['european_aqi']:
            pollen_levels = data['european_aqi']
            # Проверяем, есть ли значимые значения на сегодня (индекс > 20-30 считается заметным)
            if any(p > 20 for p in pollen_levels.get('pollen_birch', [])[:24]) or \
               any(p > 20 for p in pollen_levels.get('pollen_grass', [])[:24]) or \
               any(p > 20 for p in pollen_levels.get('pollen_ragweed', [])[:24]):
               reasons.append("Высокий уровень пыльцы в воздухе")
    except (KeyError, IndexError):
        logging.warning("Не удалось проанализировать данные по пыльце.")


    # --- Формирование итогового сообщения ---
    if not reasons:
        return "Сегодня всё спокойно, живи-балдей! 😎"
    
    if len(reasons) == 1:
        message = f"Oof! Кажется, сегодня снова ноет из-за **{reasons[0].lower()}**. Держись, друг! 😔"
        return message

    message = "Oof! Кажется, сегодня снова ноет. Держись, друг! 😔\n\nПричины:\n"
    for reason in reasons:
        message += f"• {reason}\n"
        
    return message