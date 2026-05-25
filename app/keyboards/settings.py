from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.callbacks import MainMenuCallback, SettingsCallback


def settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Часовой пояс", callback_data=SettingsCallback(action="timezone"))
    builder.button(text="🔔 Тестовое напоминание", callback_data=SettingsCallback(action="test"))
    builder.button(text="⬅️ Назад", callback_data=MainMenuCallback(action="back_main"))
    builder.adjust(1)
    return builder.as_markup()

