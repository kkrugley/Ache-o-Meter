# feedback_handler.py
"""
Вечерний опрос самочувствия пользователя.
"""
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db


async def ask_evening_feedback(bot: Bot, user_id: int, chat_id: int):
    """Отправляет вечерний опрос пользователю."""
    user = await db.get_user_by_id(user_id)
    if not user or not user.get('feedback_enabled', False):
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😊 Отлично", callback_data="feeling:1")],
        [InlineKeyboardButton(text="🙂 Нормально", callback_data="feeling:2")],
        [InlineKeyboardButton(text="😐 Так себе", callback_data="feeling:3")],
        [InlineKeyboardButton(text="😟 Плохо", callback_data="feeling:4")],
        [InlineKeyboardButton(text="😣 Ужасно", callback_data="feeling:5")],
    ])

    await bot.send_message(
        chat_id,
        "Как вы себя чувствовали сегодня?",
        reply_markup=keyboard,
    )


def get_symptoms_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора симптомов."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤕 Голова", callback_data="symptom:headache"),
            InlineKeyboardButton(text="🦴 Суставы", callback_data="symptom:joint_pain"),
        ],
        [
            InlineKeyboardButton(text="😴 Усталость", callback_data="symptom:fatigue"),
            InlineKeyboardButton(text="🫁 Дыхание", callback_data="symptom:respiratory"),
        ],
        [InlineKeyboardButton(text="🤧 Аллергия", callback_data="symptom:allergy")],
        [InlineKeyboardButton(text="👍 Ничего особенного", callback_data="symptoms_done")],
    ])
