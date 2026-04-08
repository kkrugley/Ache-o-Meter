"""Дополнительные данные о солнечной активности."""
import logging
import aiohttp


def k_to_ap(kp: float) -> float:
    """
    Конвертирует Kp-индекс в ap-индекс (линейный).
    Ap = ap * 3 (приближённо), где ap — 3-часовое значение.
    Таблица конверсии Kp → ap (стандартная IAGA):
    """
    # Упрощённая аппроксимация: ap ≈ (2^(Kp) - 1) * 10
    # Для Kp=0: 0, Kp=1: 10, Kp=2: 30, Kp=3: 70, Kp=4: 150, Kp=5: 300...
    # Используем экспоненциальную формулу, близкую к IAGA таблице
    if kp <= 0:
        return 0
    # Стандартная аппроксимация: ap = 10 * 2^(Kp/3) - 10 (грубо)
    # Более точная — lookup таблица
    kp_to_ap = {
        0: 0, 1: 3, 2: 7, 3: 15, 4: 27,
        5: 48, 6: 80, 7: 140, 8: 240, 9: 400,
    }
    # Интерполяция
    k_int = int(kp)
    k_frac = kp - k_int
    if k_int >= 9:
        return 400.0
    ap_low = kp_to_ap.get(k_int, 0)
    ap_high = kp_to_ap.get(k_int + 1, 400)
    return ap_low + (ap_high - ap_low) * k_frac


async def get_noaa_ap_index():
    """
    Ap-индекс вычисляется из Kp (NOAA не предоставляет отдельный forecast).
    Вызывается из get_forecast_data для консистентности, но данные
    будут вычислены из уже загруженных Kp-данных.
    """
    # Заглушка: Kp → Ap конвертация происходит в forecast_scoring.py
    # при наличии geo_forecast данных.
    return {'ap_forecast': []}  # будет заполнено из Kp при анализе


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
