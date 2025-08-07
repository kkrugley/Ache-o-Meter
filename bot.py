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
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()
tf = TimezoneFinder()
# Создаем планировщик, но пока не запускаем
scheduler = AsyncIOScheduler(timezone="UTC")

class SettingsState(StatesGroup):
    waiting_for_time = State()

# --- Рассылка прогнозов ---
async def send_forecast_to_user(user):
    logging.info(f"Готовлю прогноз для пользователя {user['user_id']} в городе {user['city']}")
    try:
        all_data = await fcst.get_forecast_data(user['lat'], user['lon'])
        message_text = fcst.analyze_data_and_form_message(all_data)
        await bot.send_message(user['chat_id'], message_text)
        logging.info(f"Прогноз успешно отправлен пользователю {user['user_id']}")
    except Exception as e:
        logging.error(f"Не удалось отправить прогноз пользователю {user['user_id']}: {e}", exc_info=True)

async def daily_check_and_send():
    logging.info("Планировщик: начинаю ежечасную проверку пользователей.")
    users = db.get_all_active_users()
    if not users:
        return

    for user in users:
        try:
            # Преобразуем строку часового пояса в объект timezone
            user_tz = pytz.timezone(str(user['timezone']))
            
            user_local_time = datetime.now(user_tz)
            notification_time_str = user['notification_time']
            
            # Сравниваем время в формате "ЧЧ:ММ"
            if user_local_time.strftime('%H:%M') == notification_time_str:
                logging.info(f"Время совпало для пользователя {user['user_id']}. Отправляю прогноз.")
                await send_forecast_to_user(user)
                
        except Exception as e:
            logging.error(f"Планировщик: ошибка при обработке пользователя {user['user_id']}: {e}", exc_info=True)

# --- API Геокодера ---
async def get_coords_by_city(city_name: str):
    if not YANDEX_API_KEY: return None, None, None, None
    full_url = f"https://geocode-maps.yandex.ru/1.x/?geocode={quote(city_name)}&apikey={YANDEX_API_KEY}&format=json&results=1"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(full_url) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    if data['response']['GeoObjectCollection']['featureMember']:
                        geo_object = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']
                        lon_str, lat_str = geo_object['Point']['pos'].split()
                        lat, lon = float(lat_str), float(lon_str)
                        found_city_name = geo_object['metaDataProperty']['GeocoderMetaData']['text']
                        timezone_str = tf.timezone_at(lng=lon, lat=lat)
                        return found_city_name, lat, lon, timezone_str
    except Exception: return None, None, None, None
    return None, None, None, None

# --- Обработчики команд ---
@dp.message(CommandStart())
async def handle_start(message: types.Message):
    await message.answer("Привет! Я бот 'Ache-o-Meter'. 🌦️\n\nЯ помогу тебе узнать, будешь ли ты страдать сегодня от своей метеочувствительности 😔 или нет 😊.\n\nДля начала, напиши мне, пожалуйста, название твоего города.")

@dp.message(Command('help'))
async def handle_help(message: types.Message):
    await message.answer("Вот что я умею:\n✅ Ежедневно присылаю прогноз для метеочувствительных людей.Я определяю будут ли резкие изменения в погоде, магнитные и солнечные бури, а также наличие аллергенов в воздухе.\n\nКоманды:\n/settings - изменить город или время.\n/stop - приостановить рассылку.\n/help - это сообщение.\n\nЧтобы изменить город, можно также просто написать мне его название.")

@dp.message(Command('stop'))
async def handle_stop(message: types.Message):
    db.set_user_active(message.from_user.id, is_active=False)
    await message.answer("Я понял, больше не буду беспокоить. 😴\nЕсли передумаешь, просто напиши мне название города, и подписка возобновится.")

@dp.message(Command('settings'))
async def handle_settings(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Изменить город", callback_data="change_city")], [InlineKeyboardButton(text="Изменить время", callback_data="change_time")]])
    await message.answer("Что вы хотите настроить?", reply_markup=keyboard)

@dp.callback_query(F.data == "change_city")
async def process_change_city_callback(callback: types.CallbackQuery):
    await callback.message.answer("Хорошо, просто отправь мне название нового города.")
    await callback.answer()

@dp.callback_query(F.data == "change_time")
async def process_change_time_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Понял. Отправь мне новое время для уведомлений в формате *ЧЧ:ММ* (например, 07:30 или 22:00).")
    await state.set_state(SettingsState.waiting_for_time)
    await callback.answer()

@dp.message(SettingsState.waiting_for_time, F.text)
async def process_new_time(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, '%H:%M')
        db.update_user_notification_time(message.from_user.id, message.text)
        await message.answer(f"Отлично! Новое время уведомлений установлено на *{message.text}*.")
        await state.clear()
    except ValueError:
        await message.answer("Ой, формат неправильный. Пожалуйста, попробуй еще раз в формате *ЧЧ:ММ* (например, 09:00).")

@dp.message(F.text)
async def handle_city_message(message: types.Message):
    found_city_name, lat, lon, timezone = await get_coords_by_city(message.text)
    if lat and lon and timezone:
        db.add_or_update_user(user_id=message.from_user.id, chat_id=message.chat.id, city=found_city_name, lat=lat, lon=lon, timezone=timezone)
        await message.answer(f"Отлично! Я запомнил: **{found_city_name}**. 😎\n\nТеперь ты в деле! Если хочешь изменить город или время, нажми на кнопку /settings.")
    else:
        await message.answer(f"Ой, я не могу найти место '{message.text}'. 😔\nПопробуй написать его по-другому.")

# --- Функция для "чистой" остановки ---
async def on_shutdown(dispatcher: Dispatcher):
    logging.info("Остановка бота...")
    scheduler.shutdown(wait=False)
    await dispatcher.storage.close()
    await bot.session.close()
    logging.info("Бот остановлен.")

# --- Основная функция запуска ---
async def main():
    db.init_db()
    dp.shutdown.register(on_shutdown)
    
    # "Боевой" режим: запускаем проверку раз в час в 00 минут.
    scheduler.add_job(daily_check_and_send, 'cron', hour='*', minute=0)
    
    # Отладочный режим (закомментирован):
    # scheduler.add_job(daily_check_and_send, 'interval', seconds=30)
    
    scheduler.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот выключен вручную.")