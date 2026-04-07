import asyncio
import logging
import os
from urllib.parse import quote
from datetime import datetime

import aiohttp
import pytz
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from timezonefinder import TimezoneFinder

import database as db
import forecast as fcst

# --- Инициализация и состояния ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
tf = TimezoneFinder()
scheduler = AsyncIOScheduler(timezone="UTC")

class UserState(StatesGroup):
    waiting_for_time = State()
    waiting_for_city_confirmation = State()

# --- Рассылка и отправка прогнозов ---

async def send_forecast_to_user(user_id: int, chat_id: int):
    """Готовит и отправляет прогноз конкретному пользователю."""
    user = db.get_user_by_id(user_id)
    if not user or not user['is_active']:
        logging.warning(f"Попытка отправить прогноз неактивному пользователю {user_id}")
        return

    logging.info(f"Готовлю прогноз для пользователя {user_id} в городе {user['city']}")
    try:
        all_data = await fcst.get_forecast_data(user['lat'], user['lon'])
        message_text = fcst.analyze_data_and_form_message(all_data)
        await bot.send_message(chat_id, message_text)
        logging.info(f"Прогноз успешно отправлен пользователю {user_id}")
    except Exception as e:
        logging.error(f"Не удалось отправить прогноз пользователю {user_id}: {e}", exc_info=True)

async def scheduled_check_and_send():
    """Планировщик: проверяет пользователей и отправляет им прогноз по расписанию."""
    logging.info("Планировщик: начинаю ежечасную проверку пользователей.")
    users = db.get_all_active_users()
    if not users:
        return

    for user in users:
        try:
            user_tz = pytz.timezone(str(user['timezone']))
            user_local_time = datetime.now(user_tz)
            if user_local_time.strftime('%H:%M') == user['notification_time']:
                logging.info(f"Время совпало для пользователя {user['user_id']}. Отправляю прогноз.")
                await send_forecast_to_user(user['user_id'], user['chat_id'])
        except Exception as e:
            logging.error(f"Планировщик: ошибка при обработке пользователя {user['user_id']}: {e}", exc_info=True)

# --- API Геокодера ---

async def get_coords_by_city(city_name: str):
    """Получает координаты, полное название и часовой пояс по названию города через Nominatim (OpenStreetMap)."""
    encoded_city = quote(city_name)
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded_city}&limit=1"
    headers = {"User-Agent": "Ache-o-Meter Telegram Bot"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                if data:
                    geo_object = data[0]
                    lat = float(geo_object['lat'])
                    lon = float(geo_object['lon'])
                    found_city_name = geo_object['display_name']
                    timezone_str = tf.timezone_at(lng=lon, lat=lat)
                    return found_city_name, lat, lon, timezone_str
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка при запросе к Nominatim: {e}")
    except Exception as e:
        logging.error(f"Ошибка при обработке ответа от Nominatim: {e}")
    return None, None, None, None

# --- Обработчики команд ---

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    start_text = (
        "Привет! Я бот 'Ache-o-Meter'. 🌦️\n\n"
        "Я помогу тебе узнать, стоит ли сегодня ожидать головной боли из-за погоды.\n\n"
        "Для начала, напиши мне, пожалуйста, название твоего города."
    )
    await message.answer(start_text)

@dp.message(Command('help'))
async def handle_help(message: types.Message):
    help_text = (
        "<b>Вот что я умею:</b>\n"
        "✅ Ежедневно присылаю прогноз для метеочувствительных людей.\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Начать работу с ботом.\n"
        "/settings - Изменить город или время уведомлений.\n"
        "/forecast_now - Получить прогноз немедленно.\n"
        "/stop - Приостановить рассылку.\n"
        "/info - Узнать о факторах, влияющих на самочувствие.\n"
        "/help - Показать это сообщение.\n\n"
        "Чтобы изменить город, можно также просто написать мне его название."
    )
    await message.answer(help_text)

@dp.message(Command('info'))
async def handle_info(message: types.Message):
    info_text = "<b>Я анализирую несколько ключевых факторов, которые могут влиять на ваше самочувствие:</b>\n\n"
    for key, value in fcst.PARAMETER_DESCRIPTIONS.items():
        info_text += f"{value}\n\n"
    info_text += "На основе этих данных я составляю комплексный прогноз рисков."
    await message.answer(info_text)

@dp.message(Command('stop'))
async def handle_stop(message: types.Message):
    db.set_user_active(message.from_user.id, is_active=False)
    await message.answer("Я понял, больше не буду беспокоить. 😴\nЕсли передумаешь, просто напиши мне название города, и подписка возобновится.")

@dp.message(Command('forecast_now'))
async def handle_forecast_now(message: types.Message):
    user = db.get_user_by_id(message.from_user.id)
    if user and user['is_active']:
        await message.answer("Хорошо, сейчас всё проверю и пришлю. Один момент... 🕵️")
        await send_forecast_to_user(message.from_user.id, message.chat.id)
    else:
        await message.answer("Сначала нужно зарегистрироваться. Отправь мне название своего города, чтобы я мог начать работу. /start")

@dp.message(Command('settings'))
async def handle_settings(message: types.Message):
    user = db.get_user_by_id(message.from_user.id)
    city_info = f"Ваш текущий город: <b>{user['city']}</b>." if user and user['city'] else "Город не установлен."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить город", callback_data="change_city")],
        [InlineKeyboardButton(text="Изменить время", callback_data="change_time")]
    ])
    await message.answer(f"{city_info}\nЧто вы хотите настроить?", reply_markup=keyboard)

# --- Обработка колбэков и состояний ---

@dp.callback_query(F.data == "change_city")
async def process_change_city_callback(callback: types.CallbackQuery):
    await callback.message.answer("Хорошо, просто отправь мне название нового города.")
    await callback.answer()

@dp.callback_query(F.data == "change_time")
async def process_change_time_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Понял. Отправь мне новое время для уведомлений в формате <b>ЧЧ:ММ</b> (например, 07:30 или 22:00).")
    await state.set_state(UserState.waiting_for_time)
    await callback.answer()

@dp.message(UserState.waiting_for_time, F.text)
async def process_new_time(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, '%H:%M')
        db.update_user_notification_time(message.from_user.id, message.text)
        await message.answer(f"Отлично! Новое время уведомлений установлено на <b>{message.text}</b>.")
        await state.clear()
    except ValueError:
        await message.answer("Ой, формат неправильный. Пожалуйста, попробуй еще раз в формате <b>ЧЧ:ММ</b> (например, 09:00).")

@dp.callback_query(UserState.waiting_for_city_confirmation, F.data.startswith("confirm_city_"))
async def process_city_confirmation(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split('_')[2]
    user_data = await state.get_data()

    if action == "yes":
        city_info = user_data['city_info']
        db.add_or_update_user(
            user_id=callback.from_user.id,
            chat_id=callback.message.chat.id,
            city=city_info['name'],
            lat=city_info['lat'],
            lon=city_info['lon'],
            timezone=city_info['tz']
        )
        await callback.message.edit_text(f"Отлично! Я запомнил: <b>{city_info['name']}</b>. 😎\n\nТеперь ты в деле! Если хочешь изменить настройки, используй /settings.")
    else: # action == 'no'
        await callback.message.edit_text("Понял, ничего не меняю. Если передумаешь, просто напиши мне название города.")

    await state.clear()
    await callback.answer()

# --- УМНЫЙ ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ---
@dp.message(F.text)
async def handle_text_message(message: types.Message, state: FSMContext):
    await message.answer("Ищу информацию по городу... ⏳")
    found_city_name, lat, lon, timezone = await get_coords_by_city(message.text)

    if lat and lon and timezone:
        # Сохраняем найденные данные в состояние FSM
        await state.set_data({
            'city_info': {'name': found_city_name, 'lat': lat, 'lon': lon, 'tz': timezone}
        })
        await state.set_state(UserState.waiting_for_city_confirmation)

        # Создаем клавиатуру для подтверждения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, это он", callback_data="confirm_city_yes")],
            [InlineKeyboardButton(text="❌ Нет, другой", callback_data="confirm_city_no")]
        ])
        await message.answer(f"Я нашел вот это: <b>{found_city_name}</b>. Это правильный город?", reply_markup=keyboard)
    else:
        await message.answer(f"Ой, я не могу найти место '{message.text}'. 😔\nПопробуй написать его по-другому или проверь, нет ли опечаток.")


# --- Запуск и остановка ---

async def on_shutdown(dispatcher: Dispatcher):
    logging.info("Остановка бота...")
    scheduler.shutdown(wait=False)
    await bot.session.close()
    logging.info("Бот остановлен.")

async def main():
    db.init_db()
    dp.shutdown.register(on_shutdown)
    
    scheduler.add_job(scheduled_check_and_send, 'cron', hour='*', minute=0)
    scheduler.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот выключен вручную.")