from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.callbacks import MainMenuCallback, SettingsCallback


def settings_text(timezone_name: str, note: str | None = None) -> str:
    parts = [
        "⚙️ Настройки",
        "",
        f"Часовой пояс: {timezone_name}",
    ]
    if note:
        parts.extend(["", note])
    return "\n".join(parts)


def settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🌍 Изменить часовой пояс", callback_data=SettingsCallback(action="timezone"))
    builder.button(text="🔔 Тестовое напоминание", callback_data=SettingsCallback(action="test"))
    builder.button(text="🏠 Главное меню", callback_data=MainMenuCallback(action="back_main"))
    builder.adjust(1)
    return builder.as_markup()


def timezone_prompt_text(current_timezone: str, error: str | None = None) -> str:
    parts = [
        "🌍 Изменить часовой пояс",
        "",
        f"Текущий часовой пояс: {current_timezone}",
        "",
        "Введите новый часовой пояс, например Europe/Moscow.",
    ]
    if error:
        parts.extend(["", f"Ошибка: {error}"])
    return "\n".join(parts)


def timezone_prompt_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=MainMenuCallback(action="settings"))
    builder.button(text="🏠 Главное меню", callback_data=MainMenuCallback(action="back_main"))
    builder.adjust(1)
    return builder.as_markup()
