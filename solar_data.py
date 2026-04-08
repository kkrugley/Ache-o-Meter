"""Дополнительные данные о солнечной активности."""
import logging
import aiohttp


async def get_noaa_ap_index():
    """Получает Ap-индекс (линейный, в отличие от логарифмического Kp)."""
    url = "https://services.swpc.noaa.gov/products/noaa-ap-index-forecast.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return {'ap_forecast': [
                    {'time_tag': item['time_tag'], 'ap_value': float(item['ap'])}
                    for item in data if isinstance(item, dict)
                ]}
    except Exception as e:
        logging.error(f"Ошибка Ap-индекс: {e}")
        return {}


async def get_solar_flares():
    """Получает данные о солнечных вспышках GOES X-ray."""
    url = "https://services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                # Фильтруем M и X классы
                significant = [
                    flare for flare in data
                    if isinstance(flare, dict) and flare.get('class', '').startswith(('M', 'X'))
                ]
                return {'solar_flares': significant}
    except Exception as e:
        logging.error(f"Ошибка солнечные вспышки: {e}")
        return {}
