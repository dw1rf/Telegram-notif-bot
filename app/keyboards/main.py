from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.callbacks import MainMenuCallback


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="➕ Создать напоминание",
        callback_data=MainMenuCallback(action="create"),
    )
    builder.button(
        text="📋 Мои напоминания",
        callback_data=MainMenuCallback(action="list"),
    )
    builder.button(
        text="🔁 Повторяющиеся",
        callback_data=MainMenuCallback(action="recurring"),
    )
    builder.button(
        text="⚙️ Настройки",
        callback_data=MainMenuCallback(action="settings"),
    )
    builder.adjust(1)
    return builder.as_markup()

