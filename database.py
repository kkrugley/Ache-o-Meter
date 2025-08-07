import sqlite3
import logging
import os

DB_FILE = 'data/users.db'

def init_db():
    """Инициализирует БД, создает папку и таблицу."""
    try:
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                city TEXT,
                lat REAL,
                lon REAL,
                timezone TEXT,
                is_active INTEGER DEFAULT 1,
                notification_time TEXT DEFAULT '08:00'
            )
        ''')
        conn.commit()
        conn.close()
        logging.info("База данных успешно инициализирована.")
    except Exception as e:
        logging.error(f"Ошибка при инициализации БД: {e}")

def add_or_update_user(user_id, chat_id, city, lat, lon, timezone):
    """Добавляет или обновляет пользователя, активируя подписку."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ЗДЕСЬ ---
        # При обновлении (ON CONFLICT) мы НЕ трогаем поле notification_time.
        cursor.execute('''
            INSERT INTO users (user_id, chat_id, city, lat, lon, timezone, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                city=excluded.city,
                lat=excluded.lat,
                lon=excluded.lon,
                timezone=excluded.timezone,
                is_active=1
        ''', (user_id, chat_id, city, lat, lon, timezone))
        
        conn.commit()
        conn.close()
        logging.info(f"Пользователь {user_id} сохранен/обновлен: город {city}, часовой пояс {timezone}.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении пользователя {user_id}: {e}")

def set_user_active(user_id, is_active: bool):
    """Изменяет статус подписки пользователя (активна/неактивна)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (int(is_active), user_id))
        conn.commit()
        conn.close()
        logging.info(f"Статус подписки для пользователя {user_id} изменен на {is_active}.")
    except Exception as e:
        logging.error(f"Ошибка при изменении статуса пользователя {user_id}: {e}")

def update_user_notification_time(user_id, new_time: str):
    """Обновляет время уведомлений для пользователя."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET notification_time = ? WHERE user_id = ?", (new_time, user_id))
        conn.commit()
        conn.close()
        logging.info(f"Время уведомлений для пользователя {user_id} изменено на {new_time}.")
    except Exception as e:
        logging.error(f"Ошибка при изменении времени уведомлений для {user_id}: {e}")

def get_all_active_users():
    """Возвращает список всех активных пользователей."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE is_active = 1")
        users = cursor.fetchall()
        conn.close()
        return users
    except Exception as e:
        logging.error(f"Ошибка при получении пользователей из БД: {e}")
        return []

def get_user_by_id(user_id: int):
    """Возвращает данные пользователя по его ID."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logging.error(f"Ошибка при получении пользователя {user_id} из БД: {e}")
        return None