import os
import logging
import asyncpg

_pool = None

SENSITIVITY_FIELDS = [
    'sensitivity_pressure',
    'sensitivity_temperature',
    'sensitivity_humidity',
    'sensitivity_geomagnetic',
    'sensitivity_air_quality',
    'sensitivity_uv',
    'sensitivity_apparent_temperature',
    'sensitivity_dew_point',
    'sensitivity_visibility',
    'sensitivity_storm',
    'sensitivity_freezing_level',
]

ALLERGEN_FIELDS = [
    'allergen_alder',
    'allergen_birch',
    'allergen_grass',
    'allergen_mugwort',
    'allergen_olive',
    'allergen_ragweed',
]

SENSITIVITY_LABELS = {
    'sensitivity_pressure': '🌀 Давление',
    'sensitivity_temperature': '🌡️ Температура',
    'sensitivity_humidity': '💧 Влажность',
    'sensitivity_geomagnetic': '🌌 Геомагнитная',
    'sensitivity_air_quality': '🌫️ Качество воздуха',
    'sensitivity_uv': '☀️ UV-излучение',
    'sensitivity_apparent_temperature': '🌡️ Ощущаемая температура',
    'sensitivity_dew_point': '💧 Точка росы',
    'sensitivity_visibility': '🌫️ Видимость',
    'sensitivity_storm': '⛈️ Грозовая активность',
    'sensitivity_freezing_level': '❄️ Уровень замерзания',
}

ALLERGEN_LABELS = {
    'allergen_alder': '🌳 Ольха',
    'allergen_birch': '🌳 Берёза',
    'allergen_grass': '🌿 Злаковые травы',
    'allergen_mugwort': '🌿 Полынь',
    'allergen_olive': '🫒 Олива',
    'allergen_ragweed': '🌿 Амброзия',
}

USERS_TABLE_SQL = '''
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        city TEXT,
        lat DOUBLE PRECISION,
        lon DOUBLE PRECISION,
        timezone TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        notification_time TEXT DEFAULT '08:00',
        sensitivity_pressure BOOLEAN DEFAULT TRUE,
        sensitivity_temperature BOOLEAN DEFAULT TRUE,
        sensitivity_humidity BOOLEAN DEFAULT TRUE,
        sensitivity_geomagnetic BOOLEAN DEFAULT TRUE,
        sensitivity_air_quality BOOLEAN DEFAULT TRUE,
        sensitivity_uv BOOLEAN DEFAULT TRUE,
        sensitivity_apparent_temperature BOOLEAN DEFAULT TRUE,
        sensitivity_dew_point BOOLEAN DEFAULT TRUE,
        sensitivity_visibility BOOLEAN DEFAULT TRUE,
        sensitivity_storm BOOLEAN DEFAULT TRUE,
        sensitivity_freezing_level BOOLEAN DEFAULT TRUE,
        allergen_alder BOOLEAN DEFAULT FALSE,
        allergen_birch BOOLEAN DEFAULT FALSE,
        allergen_grass BOOLEAN DEFAULT FALSE,
        allergen_mugwort BOOLEAN DEFAULT FALSE,
        allergen_olive BOOLEAN DEFAULT FALSE,
        allergen_ragweed BOOLEAN DEFAULT FALSE
    )
'''


async def init_pool():
    """Инициализирует пул подключений к PostgreSQL."""
    global _pool
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logging.error("DATABASE_URL не установлен!")
        raise RuntimeError("DATABASE_URL environment variable is required")

    try:
        _pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(USERS_TABLE_SQL)
            # Миграция: добавляем новые колонки если их нет
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_pressure', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_temperature', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_humidity', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_geomagnetic', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_air_quality', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_uv', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_apparent_temperature', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_dew_point', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_visibility', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_storm', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'sensitivity_freezing_level', 'BOOLEAN DEFAULT TRUE')
            await _add_column_if_not_exists(conn, 'users', 'allergen_alder', 'BOOLEAN DEFAULT FALSE')
            await _add_column_if_not_exists(conn, 'users', 'allergen_birch', 'BOOLEAN DEFAULT FALSE')
            await _add_column_if_not_exists(conn, 'users', 'allergen_grass', 'BOOLEAN DEFAULT FALSE')
            await _add_column_if_not_exists(conn, 'users', 'allergen_mugwort', 'BOOLEAN DEFAULT FALSE')
            await _add_column_if_not_exists(conn, 'users', 'allergen_olive', 'BOOLEAN DEFAULT FALSE')
            await _add_column_if_not_exists(conn, 'users', 'allergen_ragweed', 'BOOLEAN DEFAULT FALSE')
        logging.info("База данных PostgreSQL успешно инициализирована.")
    except Exception as e:
        logging.error(f"Ошибка при инициализации БД: {e}")
        raise


async def _add_column_if_not_exists(conn, table, column, col_type):
    """Добавляет колонку если она ещё не существует."""
    exists = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns WHERE table_name=$1 AND column_name=$2",
        table, column
    )
    if not exists:
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


async def close_pool():
    """Закрывает пул подключений."""
    global _pool
    if _pool:
        await _pool.close()
        logging.info("Пул подключений к БД закрыт.")


async def add_or_update_user(user_id, chat_id, city, lat, lon, timezone):
    """Добавляет или обновляет пользователя, активируя подписку."""
    try:
        async with _pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (user_id, chat_id, city, lat, lon, timezone, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                ON CONFLICT(user_id) DO UPDATE SET
                    city=EXCLUDED.city,
                    lat=EXCLUDED.lat,
                    lon=EXCLUDED.lon,
                    timezone=EXCLUDED.timezone,
                    is_active=TRUE
            ''', user_id, chat_id, city, lat, lon, timezone)
        logging.info(f"Пользователь {user_id} сохранен/обновлен: город {city}, часовой пояс {timezone}.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении пользователя {user_id}: {e}")


async def set_user_active(user_id, is_active: bool):
    """Изменяет статус подписки пользователя."""
    try:
        async with _pool.acquire() as conn:
            await conn.execute("UPDATE users SET is_active = $1 WHERE user_id = $2", is_active, user_id)
        logging.info(f"Статус подписки для пользователя {user_id} изменен на {is_active}.")
    except Exception as e:
        logging.error(f"Ошибка при изменении статуса пользователя {user_id}: {e}")


async def update_user_notification_time(user_id, new_time: str):
    """Обновляет время уведомлений для пользователя."""
    try:
        async with _pool.acquire() as conn:
            await conn.execute("UPDATE users SET notification_time = $1 WHERE user_id = $2", new_time, user_id)
        logging.info(f"Время уведомлений для пользователя {user_id} изменено на {new_time}.")
    except Exception as e:
        logging.error(f"Ошибка при изменении времени уведомлений для {user_id}: {e}")


async def update_user_sensitivity(user_id, field: str, value: bool):
    """Обновляет флаг чувствительности пользователя."""
    if field not in SENSITIVITY_FIELDS:
        logging.error(f"Неизвестное поле чувствительности: {field}")
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(f"UPDATE users SET {field} = $1 WHERE user_id = $2", value, user_id)
        logging.info(f"Чувствительность {field} для пользователя {user_id} = {value}.")
    except Exception as e:
        logging.error(f"Ошибка при обновлении чувствительности {field} для {user_id}: {e}")


async def update_user_allergen(user_id, field: str, value: bool):
    """Обновляет флаг аллергена пользователя."""
    if field not in ALLERGEN_FIELDS:
        logging.error(f"Неизвестное поле аллергена: {field}")
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(f"UPDATE users SET {field} = $1 WHERE user_id = $2", value, user_id)
        logging.info(f"Аллерген {field} для пользователя {user_id} = {value}.")
    except Exception as e:
        logging.error(f"Ошибка при обновлении аллергена {field} для {user_id}: {e}")


async def get_all_active_users():
    """Возвращает список всех активных пользователей."""
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users WHERE is_active = TRUE")
            return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"Ошибка при получении пользователей из БД: {e}")
        return []


async def get_user_by_id(user_id: int):
    """Возвращает данные пользователя по его ID."""
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            return dict(row) if row else None
    except Exception as e:
        logging.error(f"Ошибка при получении пользователя {user_id} из БД: {e}")
        return None
