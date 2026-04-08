"""
Взвешенная scoring-модель для анализа метеорологических рисков.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# Веса факторов (будут калиброваться через обратную связь)
FACTOR_WEIGHTS = {
    'pressure_change': 1.5,
    'pressure_rate': 1.3,
    'temperature_change': 1.0,
    'geomagnetic_kp': 1.2,
    'humidity': 0.6,
    'pm25': 0.8,
    'pm10': 0.5,
    'o3': 0.6,
    'no2': 0.4,
    'uv': 0.5,
    'apparent_temperature': 0.7,
    'dew_point': 0.6,
    'visibility': 0.3,
    'storm_cape': 0.8,
    'freezing_level': 0.4,
    'pollen_per_allergen': 1.4,
}


RISK_THRESHOLDS = [
    (0, 5, 'Благоприятно', '🟢'),
    (5, 12, 'Небольшой риск', '🟡 мягкий'),
    (12, 20, 'Средний риск', '🟡'),
    (20, 30, 'Высокий риск', '🟠'),
    (30, float('inf'), 'Очень высокий риск', '🔴'),
]


COMBO_BONUSES = [
    {
        'name': 'Давление↓ + Kp≥4',
        'condition': lambda scores: scores.get('pressure_change', 0) > 0 and scores.get('geomagnetic_kp', 0) >= 4,
        'bonus': 3,
    },
    {
        'name': 'Высокая влажность + высокая t° + высокая точка росы',
        'condition': lambda scores: scores.get('humidity', 0) > 3 and scores.get('apparent_temperature', 0) > 3 and scores.get('dew_point', 0) > 3,
        'bonus': 3,
    },
    {
        'name': 'PM2.5 ↑ + O₃ ↑',
        'condition': lambda scores: scores.get('pm25', 0) > 3 and scores.get('o3', 0) > 3,
        'bonus': 2,
    },
    {
        'name': 'Давление↓ + CAPE ↑',
        'condition': lambda scores: scores.get('pressure_change', 0) > 0 and scores.get('storm_cape', 0) > 3,
        'bonus': 2,
    },
    {
        'name': 'Температура↓ резко + Влажность↑',
        'condition': lambda scores: scores.get('temperature_change', 0) > 4 and scores.get('humidity', 0) > 3,
        'bonus': 2,
    },
    {
        'name': 'Пыльца ↑ + PM2.5 ↑',
        'condition': lambda scores: scores.get('pollen', 0) > 3 and scores.get('pm25', 0) > 3,
        'bonus': 2,
    },
]


def get_risk_level(total_score: float) -> tuple[str, str]:
    """Возвращает (уровень риска, emoji) по порогам."""
    for low, high, level, emoji in RISK_THRESHOLDS:
        if low <= total_score < high:
            return level, emoji
    return 'Очень высокий риск', '🔴'


def score_pressure_change(pressure_values, times, current_idx, is_falling, climate_normals=None):
    """Scoring для изменения давления. Возвращает (score: 0-10, details: dict)."""
    if not pressure_values or current_idx >= len(pressure_values):
        return 0.0, {}

    HPA_TO_MMHG = 0.750062
    current = pressure_values[current_idx]
    future = pressure_values[current_idx + 1:] if current_idx + 1 < len(pressure_values) else []

    if not future:
        return 0.0, {}

    max_change = max(abs(p - current) for p in future) * HPA_TO_MMHG

    score = 0.0
    if max_change > 10:
        score = 10
    elif max_change > 8:
        score = 8
    elif max_change > 5:
        score = 6
    elif max_change > 3:
        score = 4
    elif max_change > 1.5:
        score = 2

    if is_falling:
        score = min(score * 1.3, 10)

    anomaly_factor = 1.0
    if climate_normals:
        normal_std = climate_normals.get('pressure_std', 0)
        if normal_std > 0:
            anomaly = max_change / (normal_std * HPA_TO_MMHG)
            anomaly_factor = min(anomaly, 2.0)
            score = min(score * anomaly_factor, 10)

    return round(score, 1), {
        'change_mmhg': round(max_change, 1),
        'direction': 'falling' if is_falling else 'rising',
        'anomaly_factor': round(anomaly_factor, 2) if climate_normals else None,
    }


def score_pressure_rate(pressure_values, times, window_hours=3):
    """Scoring для скорости изменения давления (скользящее окно)."""
    from forecast import max_rate_of_change

    HPA_TO_MMHG = 0.750062
    values_mmhg = [p * HPA_TO_MMHG for p in pressure_values]
    max_rate, peak_time = max_rate_of_change(values_mmhg, times, window_hours)

    score = 0.0
    if max_rate > 1.5:
        score = 9
    elif max_rate > 1.0:
        score = 6
    elif max_rate > 0.5:
        score = 3

    return round(score, 1), {
        'rate_mmhg_h': round(max_rate, 2),
        'peak_time': peak_time.strftime('%H:%M') if peak_time else None,
    }


def score_temperature_change(today_max, yesterday_max):
    diff = abs(today_max - yesterday_max)
    score = 0.0
    if diff > 10:
        score = 9
    elif diff > 7:
        score = 7
    elif diff > 5:
        score = 5
    elif diff > 3:
        score = 2
    return round(score, 1), {'diff_c': round(diff, 1), 'today_max': round(today_max, 1), 'yesterday_max': round(yesterday_max, 1)}


def score_geomagnetic(max_kp):
    score = 0.0
    if max_kp >= 7:
        score = 10
    elif max_kp >= 5:
        score = 7
    elif max_kp >= 4:
        score = 4
    elif max_kp >= 3:
        score = 1
    return round(score, 1), {'kp_max': int(max_kp) if max_kp else 0}


def score_air_quality(pm25_avg, pm10_avg, o3_avg, no2_avg):
    scores = {}
    scores['pm25'] = 8 if pm25_avg > 35 else (4 if pm25_avg > 15 else 0)
    scores['pm10'] = 5 if pm10_avg > 50 else 0
    scores['o3'] = 7 if o3_avg > 120 else (4 if o3_avg > 100 else 0)
    scores['no2'] = 3 if no2_avg > 40 else 0
    details = {'pm25_avg': round(pm25_avg, 1), 'pm10_avg': round(pm10_avg, 1), 'o3_avg': round(o3_avg, 1), 'no2_avg': round(no2_avg, 1)}
    return scores, details


def score_uv(max_uv):
    score = 0.0
    if max_uv >= 11: score = 10
    elif max_uv >= 8: score = 7
    elif max_uv >= 5: score = 4
    elif max_uv >= 3: score = 2
    return round(score, 1), {'uv_max': round(max_uv, 1)}


def score_humidity(avg_humidity):
    score = 0.0
    if avg_humidity > 90: score = 6
    elif avg_humidity > 85: score = 3
    elif avg_humidity < 20: score = 5
    elif avg_humidity < 30: score = 2
    return round(score, 1), {'humidity_avg': round(avg_humidity, 1)}


def score_apparent_temperature(max_diff):
    score = 0.0
    if max_diff > 10: score = 8
    elif max_diff > 8: score = 6
    elif max_diff > 5: score = 3
    return round(score, 1), {'apparent_temp_diff_max': round(max_diff, 1)}


def score_dew_point(max_dew, min_dew):
    score = 0.0
    if max_dew > 22: score = 6
    elif max_dew > 20: score = 4
    elif max_dew > 16: score = 2
    if min_dew < -20: score = max(score, 4)
    elif min_dew < -15: score = max(score, 2)
    return round(score, 1), {'dew_point_max': round(max_dew, 1), 'dew_point_min': round(min_dew, 1)}


def score_visibility(min_visibility_m):
    score = 0.0
    if min_visibility_m < 200: score = 8
    elif min_visibility_m < 1000: score = 5
    elif min_visibility_m < 5000: score = 2
    return round(score, 1), {'visibility_min_km': round(min_visibility_m / 1000, 1)}


def score_storm(max_cape):
    score = 0.0
    if max_cape > 3500: score = 9
    elif max_cape > 2500: score = 7
    elif max_cape > 1000: score = 4
    elif max_cape > 500: score = 2
    return round(score, 1), {'cape_max': int(max_cape)}


def score_freezing_level(fl_change):
    score = 0.0
    if fl_change > 800: score = 5
    elif fl_change > 500: score = 2
    return round(score, 1), {'freezing_level_change': int(fl_change)}


def score_pollen(max_pollen):
    score = 0.0
    if max_pollen > 100: score = 9
    elif max_pollen > 50: score = 7
    elif max_pollen > 20: score = 4
    elif max_pollen > 5: score = 1
    return round(score, 1), {'pollen_max': round(max_pollen, 1)}


def calculate_risk_score(data, user_profile, climate_normals=None):
    """
    Новая scoring-функция.
    Возвращает dict с total_score, risk_level, emoji, factors, combos, stats, peak_hours.
    """
    if not data:
        return {"error": True}

    user_tz = user_profile.get('timezone', 'UTC') if user_profile else 'UTC'
    now = datetime.now(ZoneInfo(user_tz))

    weather_hourly = data.get('weather', {}).get('hourly', {})
    air_hourly = data.get('air_quality', {}).get('hourly', {})
    weather_times_str = weather_hourly.get('time', [])
    air_times_str = air_hourly.get('time', [])
    geo_forecast = data.get('geo', {}).get('geo_forecast', [])

    from forecast import parse_timezone_aware
    weather_times = [parse_timezone_aware(t, user_tz) for t in weather_times_str]
    air_times = [parse_timezone_aware(t, user_tz) for t in air_times_str]

    factors = []
    stats = {}
    individual_scores = {}
    sensitivities = _get_sensitivities(user_profile)

    # 1. Давление — изменение
    if sensitivities.get('pressure'):
        pressures = weather_hourly.get('surface_pressure', [])
        if pressures and weather_times:
            hpa_to_mmhg = 0.750062
            current_idx = 0
            for i, t in enumerate(weather_times):
                if t >= now:
                    current_idx = i
                    break

            if current_idx > 0 and current_idx < len(pressures):
                past = [(t, p) for t, p in zip(weather_times[:current_idx], pressures[:current_idx])
                        if now - timedelta(hours=24) <= t < now and p is not None]
                future = [(t, p) for t, p in zip(weather_times[current_idx:], pressures[current_idx:])
                          if now <= t < now + timedelta(hours=24) and p is not None]

                if past and future:
                    current_pressure = past[-1][1]
                    future_pressures = [p for _, p in future]
                    avg_future = sum(future_pressures) / len(future_pressures)
                    is_falling = avg_future < current_pressure

                    score, detail = score_pressure_change(
                        pressures, weather_times, current_idx - 1, is_falling, climate_normals
                    )
                    weight = FACTOR_WEIGHTS['pressure_change']
                    factors.append({
                        'name': '🌀 Давление (изменение)',
                        'score': score, 'weight': weight,
                        'weighted': round(score * weight, 1),
                        'detail': f"Δ{detail.get('change_mmhg', 0)} мм рт. ст., {detail.get('direction', '')}",
                    })
                    individual_scores['pressure_change'] = score
                    stats['pressure_change_mmhg'] = detail.get('change_mmhg', 0)
                    stats['pressure_direction'] = detail.get('direction', '')

    # 2. Давление — скорость
    if sensitivities.get('pressure'):
        pressures = weather_hourly.get('surface_pressure', [])
        if pressures and weather_times:
            window_points = [(t, p) for t, p in zip(weather_times, pressures)
                             if now - timedelta(hours=6) <= t <= now + timedelta(hours=6) and p is not None]
            if len(window_points) >= 2:
                w_times = [t for t, _ in window_points]
                w_pressures = [p for _, p in window_points]
                score, detail = score_pressure_rate(w_pressures, w_times)
                weight = FACTOR_WEIGHTS['pressure_rate']
                factors.append({
                    'name': '⏱️ Давление (скорость)',
                    'score': score, 'weight': weight,
                    'weighted': round(score * weight, 1),
                    'detail': f"{detail.get('rate_mmhg_h', 0)} мм/ч",
                })
                individual_scores['pressure_rate'] = score
                if detail.get('peak_time'):
                    stats['pressure_rate_peak'] = detail['peak_time']

    # 3. Температура
    if sensitivities.get('temperature'):
        daily = data.get('weather', {}).get('daily', {})
        temp_max_list = daily.get('temperature_2m_max', [])
        if len(temp_max_list) >= 2:
            today_max = temp_max_list[1] if len(temp_max_list) > 1 else temp_max_list[0]
            yesterday_max = temp_max_list[0]
            score, detail = score_temperature_change(today_max, yesterday_max)
            weight = FACTOR_WEIGHTS['temperature_change']
            factors.append({
                'name': '🌡️ Температура (Δ день)',
                'score': score, 'weight': weight,
                'weighted': round(score * weight, 1),
                'detail': f"сегодня {detail['today_max']}°C / вчера {detail['yesterday_max']}°C (Δ{detail['diff_c']}°C)",
            })
            individual_scores['temperature_change'] = score
            stats['temp_diff'] = detail['diff_c']

    # 4. Геомагнитная (Kp)
    if sensitivities.get('geomagnetic'):
        max_kp = 0
        future_limit = now.replace(tzinfo=ZoneInfo('UTC')) + timedelta(hours=24)
        for fc in geo_forecast:
            ft = datetime.fromisoformat(fc['time_tag'].replace('Z', '+00:00'))
            if ft < future_limit and fc['kp_value'] > max_kp:
                max_kp = fc['kp_value']
        if max_kp > 0:
            score, detail = score_geomagnetic(max_kp)
            weight = FACTOR_WEIGHTS['geomagnetic_kp']
            factors.append({
                'name': '🌌 Геомагнитная (Kp)',
                'score': score, 'weight': weight,
                'weighted': round(score * weight, 1),
                'detail': f"Kp макс {detail['kp_max']}",
            })
            individual_scores['geomagnetic_kp'] = score
            stats['kp_max'] = detail['kp_max']

    # 5. Влажность
    if sensitivities.get('humidity'):
        humidity = weather_hourly.get('relative_humidity_2m', [])
        next_24h = [h for t, h in zip(weather_times, humidity)
                    if now <= t < now + timedelta(hours=24) and h is not None]
        if next_24h:
            avg_h = sum(next_24h) / len(next_24h)
            score, detail = score_humidity(avg_h)
            weight = FACTOR_WEIGHTS['humidity']
            factors.append({
                'name': '💧 Влажность', 'score': score, 'weight': weight,
                'weighted': round(score * weight, 1),
                'detail': f"средняя {detail['humidity_avg']}%",
            })
            individual_scores['humidity'] = score
            stats['humidity_avg'] = detail['humidity_avg']

    # 6. Качество воздуха (PM2.5, PM10, O3, NO2)
    if sensitivities.get('air_quality'):
        pm25_list = [v for t, v in zip(air_times, air_hourly.get('pm2_5', [])) if now <= t < now + timedelta(hours=24) and v is not None]
        pm10_list = [v for t, v in zip(air_times, air_hourly.get('pm10', [])) if now <= t < now + timedelta(hours=24) and v is not None]
        o3_list = [v for t, v in zip(air_times, air_hourly.get('ozone', [])) if now <= t < now + timedelta(hours=24) and v is not None]
        no2_list = [v for t, v in zip(air_times, air_hourly.get('nitrogen_dioxide', [])) if now <= t < now + timedelta(hours=24) and v is not None]

        pm25_avg = sum(pm25_list) / len(pm25_list) if pm25_list else 0
        pm10_avg = sum(pm10_list) / len(pm10_list) if pm10_list else 0
        o3_avg = sum(o3_list) / len(o3_list) if o3_list else 0
        no2_avg = sum(no2_list) / len(no2_list) if no2_list else 0

        scores, details = score_air_quality(pm25_avg, pm10_avg, o3_avg, no2_avg)

        for key, label, weight_key in [('pm25', 'PM2.5', 'pm25'), ('pm10', 'PM10', 'pm10'), ('o3', 'Озон O₃', 'o3'), ('no2', 'NO₂', 'no2')]:
            s = scores.get(key, 0)
            weight = FACTOR_WEIGHTS[weight_key]
            factors.append({
                'name': f'🌫️ {label}', 'score': s, 'weight': weight,
                'weighted': round(s * weight, 1),
                'detail': f"среднее {details[f'{key}_avg']} мкг/м³",
            })
            individual_scores[weight_key] = s
            stats[f'{key}_avg'] = details[f'{key}_avg']

    # 7. UV
    if sensitivities.get('uv'):
        uv_list = [v for t, v in zip(air_times, air_hourly.get('uv_index', [])) if now <= t < now + timedelta(hours=24) and v is not None]
        if uv_list:
            max_uv = max(uv_list)
            score, detail = score_uv(max_uv)
            weight = FACTOR_WEIGHTS['uv']
            factors.append({
                'name': '☀️ UV-индекс', 'score': score, 'weight': weight,
                'weighted': round(score * weight, 1), 'detail': f"макс {detail['uv_max']}",
            })
            individual_scores['uv'] = score
            stats['uv_max'] = detail['uv_max']

    # 8. Ощущаемая температура
    if sensitivities.get('apparent_temperature'):
        real_temps = weather_hourly.get('temperature_2m', [])
        apparent_temps = weather_hourly.get('apparent_temperature', [])
        diffs = []
        for t, r, a in zip(weather_times, real_temps, apparent_temps):
            if now <= t < now + timedelta(hours=24) and r is not None and a is not None:
                diffs.append(abs(r - a))
        if diffs:
            max_diff = max(diffs)
            score, detail = score_apparent_temperature(max_diff)
            weight = FACTOR_WEIGHTS['apparent_temperature']
            factors.append({
                'name': '🌡️ Ощущаемая t°', 'score': score, 'weight': weight,
                'weighted': round(score * weight, 1),
                'detail': f"разница до {detail['apparent_temp_diff_max']}°C",
            })
            individual_scores['apparent_temperature'] = score
            stats['apparent_temp_diff_max'] = detail['apparent_temp_diff_max']

    # 9. Точка росы
    if sensitivities.get('dew_point'):
        dew_list = [v for t, v in zip(weather_times, weather_hourly.get('dew_point_2m', [])) if now <= t < now + timedelta(hours=24) and v is not None]
        if dew_list:
            score, detail = score_dew_point(max(dew_list), min(dew_list))
            weight = FACTOR_WEIGHTS['dew_point']
            factors.append({
                'name': '💧 Точка росы', 'score': score, 'weight': weight,
                'weighted': round(score * weight, 1),
                'detail': f"от {detail['dew_point_min']}°C до {detail['dew_point_max']}°C",
            })
            individual_scores['dew_point'] = score
            stats['dew_point_max'] = detail['dew_point_max']
            stats['dew_point_min'] = detail['dew_point_min']

    # 10. Видимость
    if sensitivities.get('visibility'):
        vis_list = [v for t, v in zip(weather_times, weather_hourly.get('visibility', [])) if now <= t < now + timedelta(hours=24) and v is not None]
        if vis_list:
            score, detail = score_visibility(min(vis_list))
            weight = FACTOR_WEIGHTS['visibility']
            factors.append({
                'name': '🌫️ Видимость', 'score': score, 'weight': weight,
                'weighted': round(score * weight, 1),
                'detail': f"мин {detail['visibility_min_km']} км",
            })
            individual_scores['visibility'] = score
            stats['visibility_min_km'] = detail['visibility_min_km']

    # 11. CAPE
    if sensitivities.get('storm'):
        cape_list = [v for t, v in zip(weather_times, weather_hourly.get('cape', [])) if now <= t < now + timedelta(hours=24) and v is not None]
        if cape_list:
            score, detail = score_storm(max(cape_list))
            weight = FACTOR_WEIGHTS['storm_cape']
            factors.append({
                'name': '⛈️ CAPE (гроза)', 'score': score, 'weight': weight,
                'weighted': round(score * weight, 1),
                'detail': f"макс {detail['cape_max']} J/kg",
            })
            individual_scores['storm_cape'] = score
            stats['cape_max'] = detail['cape_max']

    # 12. Уровень замерзания
    if sensitivities.get('freezing_level'):
        fl_list = [v for t, v in zip(weather_times, weather_hourly.get('freezing_level_height', [])) if now <= t < now + timedelta(hours=24) and v is not None]
        if len(fl_list) >= 2:
            fl_change = abs(max(fl_list) - min(fl_list))
            score, detail = score_freezing_level(fl_change)
            weight = FACTOR_WEIGHTS['freezing_level']
            factors.append({
                'name': '❄️ Уровень замерзания', 'score': score, 'weight': weight,
                'weighted': round(score * weight, 1),
                'detail': f"изменение {detail['freezing_level_change']} м",
            })
            individual_scores['freezing_level'] = score
            stats['freezing_level_change'] = detail['freezing_level_change']

    # 13. Пыльца (per allergen)
    allergens = _get_allergens(user_profile)
    pollen_map = {
        'alder': 'alder_pollen', 'birch': 'birch_pollen', 'grass': 'grass_pollen',
        'mugwort': 'mugwort_pollen', 'olive': 'olive_pollen', 'ragweed': 'ragweed_pollen',
    }
    pollen_names_ru = {
        'alder': 'ольхи', 'birch': 'берёзы', 'grass': 'злаковых трав',
        'mugwort': 'полыни', 'olive': 'оливы', 'ragweed': 'амброзии',
    }
    max_pollen_score = 0
    for allergen_key, is_active in allergens.items():
        if not is_active:
            continue
        api_key = pollen_map.get(allergen_key)
        if not api_key:
            continue
        pollen_list = [v for t, v in zip(air_times, air_hourly.get(api_key, [])) if now <= t < now + timedelta(hours=24) and v is not None]
        if pollen_list:
            max_p = max(pollen_list)
            score, detail = score_pollen(max_p)
            weight = FACTOR_WEIGHTS['pollen_per_allergen']
            factors.append({
                'name': f'🌿 Пыльца ({pollen_names_ru[allergen_key]})',
                'score': score, 'weight': weight,
                'weighted': round(score * weight, 1),
                'detail': f"макс {round(max_p, 1)} grains/m³",
            })
            max_pollen_score = max(max_pollen_score, score)
            stats[f'pollen_{allergen_key}'] = round(max_p, 1)

    individual_scores['pollen'] = max_pollen_score

    # === Подсчёт итогового балла ===
    total_weighted = sum(f['weighted'] for f in factors)

    # Мультипликативные комбинации
    combos = []
    for combo in COMBO_BONUSES:
        if combo['condition'](individual_scores):
            combos.append({'name': combo['name'], 'bonus': combo['bonus'], 'detail': ''})
            total_weighted += combo['bonus']

    risk_level, emoji = get_risk_level(total_weighted)

    # Определяем пиковое окно
    peak_hours = _find_peak_hours(weather_times, weather_hourly, now, user_tz)

    return {
        'total_score': round(total_weighted, 1),
        'risk_level': risk_level,
        'emoji': emoji,
        'factors': factors,
        'combos': combos,
        'stats': stats,
        'peak_hours': peak_hours,
    }


def _get_sensitivities(user_profile):
    defaults = {
        'pressure': True, 'temperature': True, 'humidity': True,
        'geomagnetic': True, 'air_quality': True, 'uv': True,
        'apparent_temperature': True, 'dew_point': True, 'visibility': True,
        'storm': True, 'freezing_level': True,
    }
    if not user_profile:
        return defaults
    for key in defaults:
        db_key = f'sensitivity_{key}' if key != 'uv' else 'sensitivity_uv'
        if db_key in user_profile:
            defaults[key] = bool(user_profile[db_key])
    return defaults


def _get_allergens(user_profile):
    defaults = {
        'alder': False, 'birch': False, 'grass': False,
        'mugwort': False, 'olive': False, 'ragweed': False,
    }
    if not user_profile:
        return defaults
    for key in defaults:
        db_key = f'allergen_{key}'
        if db_key in user_profile:
            defaults[key] = bool(user_profile[db_key])
    return defaults


def _find_peak_hours(weather_times, weather_hourly, now, user_tz):
    """Находит диапазон часов с наихудшим суммарным score."""
    pressures = weather_hourly.get('surface_pressure', [])
    if not pressures:
        return None

    HPA_TO_MMHG = 0.750062
    worst_window = None
    worst_score = 0

    for i in range(len(weather_times)):
        if weather_times[i] < now:
            continue
        window_end = min(i + 4, len(weather_times))
        if window_end <= i:
            continue

        window_pressures = pressures[i:window_end]
        current = pressures[0] if pressures else 1013
        max_change = max(abs(p - current) * HPA_TO_MMHG for p in window_pressures)

        if max_change > worst_score:
            worst_score = max_change
            start_t = weather_times[i].astimezone(ZoneInfo(user_tz))
            end_t = weather_times[window_end - 1].astimezone(ZoneInfo(user_tz))
            worst_window = f"{start_t.strftime('%H:%M')}–{end_t.strftime('%H:%M')}"

    return worst_window
