from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import Reminder, RepeatType
from app.keyboards.callbacks import (
    ConfirmReminderCallback,
    MainMenuCallback,
    QuickTimeCallback,
    ReminderActionCallback,
    ReminderPageCallback,
    RepeatChoiceCallback,
)
from app.utils.timezone import format_user_datetime


REPEAT_LABELS = {
    RepeatType.NONE: "не повторять",
    RepeatType.DAILY: "каждый день",
    RepeatType.WEEKLY: "каждую неделю",
    RepeatType.MONTHLY: "каждый месяц",
}


def main_menu_text() -> str:
    return "🔔 Напоминалка\n\nВыберите действие:"


def create_text_screen(error: str | None = None) -> str:
    parts = ["📝 Новое напоминание", "", "Введите текст напоминания."]
    if error:
        parts.extend(["", error])
    return "\n".join(parts)


def create_text_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=ConfirmReminderCallback(action="cancel"))
    return builder.as_markup()


def _back_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=ConfirmReminderCallback(action="back"))
    builder.button(text="❌ Отмена", callback_data=ConfirmReminderCallback(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def quick_time_screen(text: str) -> str:
    return f"🕒 Когда напомнить?\n\nТекст: {text}"


def quick_time_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Через 10 минут", callback_data=QuickTimeCallback(value="10m"))
    builder.button(text="Через 30 минут", callback_data=QuickTimeCallback(value="30m"))
    builder.button(text="Через 1 час", callback_data=QuickTimeCallback(value="1h"))
    builder.button(text="Сегодня вечером", callback_data=QuickTimeCallback(value="evening"))
    builder.button(text="Завтра утром", callback_data=QuickTimeCallback(value="tomorrow_morning"))
    builder.button(text="📅 Ввести вручную", callback_data=QuickTimeCallback(value="manual"))
    builder.button(text="⬅️ Назад", callback_data=ConfirmReminderCallback(action="back"))
    builder.button(text="❌ Отмена", callback_data=ConfirmReminderCallback(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def manual_time_screen(error: str | None = None) -> str:
    parts = [
        "Введите время одним из способов:",
        "",
        "25.05.2026 21:00",
        "завтра 18:00",
        "сегодня 19:30",
        "через 2 часа",
        "через 15 минут",
    ]
    if error:
        parts.extend(["", f"Ошибка: {error}"])
    return "\n".join(parts)


def manual_time_keyboard() -> InlineKeyboardMarkup:
    return _back_cancel_keyboard()


def repeat_screen(text: str, remind_at, timezone_name: str) -> str:
    return (
        "🔁 Повторять?\n\n"
        f"Текст: {text}\n"
        f"Время: {format_user_datetime(remind_at, timezone_name)}"
    )


def repeat_keyboard(include_back: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Не повторять", callback_data=RepeatChoiceCallback(value=RepeatType.NONE.value))
    builder.button(text="Каждый день", callback_data=RepeatChoiceCallback(value=RepeatType.DAILY.value))
    builder.button(text="Каждую неделю", callback_data=RepeatChoiceCallback(value=RepeatType.WEEKLY.value))
    builder.button(text="Каждый месяц", callback_data=RepeatChoiceCallback(value=RepeatType.MONTHLY.value))
    if include_back:
        builder.button(text="⬅️ Назад", callback_data=ConfirmReminderCallback(action="back"))
        builder.button(text="❌ Отмена", callback_data=ConfirmReminderCallback(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def confirmation_text(
    text: str,
    remind_at,
    repeat_type: RepeatType,
    timezone_name: str,
) -> str:
    return (
        "✅ Проверьте напоминание\n\n"
        f"Текст: {text}\n"
        f"Время: {format_user_datetime(remind_at, timezone_name)}\n"
        f"Повтор: {REPEAT_LABELS[repeat_type]}"
    )


def confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сохранить", callback_data=ConfirmReminderCallback(action="save"))
    builder.button(text="✏️ Изменить текст", callback_data=ConfirmReminderCallback(action="edit_text"))
    builder.button(text="🕒 Изменить время", callback_data=ConfirmReminderCallback(action="edit_time"))
    builder.button(text="🔁 Изменить повтор", callback_data=ConfirmReminderCallback(action="edit_repeat"))
    builder.button(text="❌ Отмена", callback_data=ConfirmReminderCallback(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def saved_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои напоминания", callback_data=MainMenuCallback(action="list"))
    builder.button(text="➕ Создать ещё", callback_data=MainMenuCallback(action="create"))
    builder.button(text="🏠 Главное меню", callback_data=MainMenuCallback(action="back_main"))
    builder.adjust(1)
    return builder.as_markup()


def reminder_detail_text(reminder: Reminder, timezone_name: str) -> str:
    status = "активно" if reminder.is_active else "завершено"
    return (
        "🔔 Напоминание\n\n"
        f"Текст: {reminder.text}\n"
        f"Время: {format_user_datetime(reminder.remind_at, timezone_name)}\n"
        f"Повтор: {REPEAT_LABELS[reminder.repeat_type]}\n"
        f"Статус: {status}"
    )


def reminders_list_text(reminders: list[Reminder], timezone_name: str, title: str) -> str:
    if not reminders:
        return f"{title}\n\nСписок пуст."

    lines = [title, ""]
    for index, reminder in enumerate(reminders, start=1):
        lines.append(f"{index}. {reminder.text}")
        lines.append(f"   {format_user_datetime(reminder.remind_at, timezone_name)}")
        lines.append(f"   Повтор: {REPEAT_LABELS[reminder.repeat_type]}")
        lines.append("")
    return "\n".join(lines).strip()


def reminders_list_keyboard(
    reminders: list[Reminder],
    scope: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        InlineKeyboardButton(
            text=str(index),
            callback_data=ReminderActionCallback(
                action="open",
                reminder_id=reminder.id,
                scope=scope,
                page=page,
            ).pack(),
        )
        for index, reminder in enumerate(reminders, start=1)
    ]
    if buttons:
        builder.row(*buttons)

    if total_pages > 1:
        builder.row(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=ReminderPageCallback(scope=scope, page=max(page - 1, 1)).pack(),
            ),
            InlineKeyboardButton(
                text=f"{page}/{total_pages}",
                callback_data=MainMenuCallback(action="noop").pack(),
            ),
            InlineKeyboardButton(
                text="➡️",
                callback_data=ReminderPageCallback(scope=scope, page=min(page + 1, total_pages)).pack(),
            ),
        )

    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data=MainMenuCallback(action="back_main").pack(),
        )
    )
    return builder.as_markup()


def reminder_manage_keyboard(reminder_id: int, scope: str, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✏️ Изменить текст",
        callback_data=ReminderActionCallback(action="edit_text", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="🕒 Изменить время",
        callback_data=ReminderActionCallback(action="edit_time", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="🔁 Изменить повтор",
        callback_data=ReminderActionCallback(action="edit_repeat", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="⏰ Отложить",
        callback_data=ReminderActionCallback(action="snooze_menu", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="🗑 Удалить",
        callback_data=ReminderActionCallback(action="delete_prompt", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="⬅️ К списку",
        callback_data=ReminderPageCallback(scope=scope, page=page),
    )
    builder.button(
        text="🏠 Главное меню",
        callback_data=MainMenuCallback(action="back_main"),
    )
    builder.adjust(1)
    return builder.as_markup()


def fired_reminder_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Выполнено",
        callback_data=ReminderActionCallback(action="done", reminder_id=reminder_id, scope="fired"),
    )
    builder.button(
        text="⏰ Отложить на 10 минут",
        callback_data=ReminderActionCallback(action="snooze_10", reminder_id=reminder_id, scope="fired"),
    )
    builder.button(
        text="🕐 Отложить на 1 час",
        callback_data=ReminderActionCallback(action="snooze_60", reminder_id=reminder_id, scope="fired"),
    )
    builder.button(
        text="📅 Перенести",
        callback_data=ReminderActionCallback(action="snooze_manual", reminder_id=reminder_id, scope="fired"),
    )
    builder.button(
        text="🗑 Удалить",
        callback_data=ReminderActionCallback(action="delete_prompt", reminder_id=reminder_id, scope="fired"),
    )
    builder.adjust(1)
    return builder.as_markup()


def delete_confirm_text(reminder: Reminder) -> str:
    return f"🗑 Удалить напоминание?\n\n{reminder.text}"


def delete_confirm_keyboard(reminder_id: int, scope: str, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Да, удалить",
        callback_data=ReminderActionCallback(action="delete_confirm", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="⬅️ Нет, назад",
        callback_data=ReminderActionCallback(action="open", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.adjust(1)
    return builder.as_markup()


def deleted_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои напоминания", callback_data=MainMenuCallback(action="list"))
    builder.button(text="🏠 Главное меню", callback_data=MainMenuCallback(action="back_main"))
    builder.adjust(1)
    return builder.as_markup()


def snooze_text(reminder: Reminder) -> str:
    return f"⏰ Отложить напоминание\n\n{reminder.text}"


def snooze_keyboard(reminder_id: int, scope: str, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="На 10 минут",
        callback_data=ReminderActionCallback(action="snooze_10", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="На 30 минут",
        callback_data=ReminderActionCallback(action="snooze_30", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="На 1 час",
        callback_data=ReminderActionCallback(action="snooze_60", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="На завтра",
        callback_data=ReminderActionCallback(action="snooze_tomorrow", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="📅 Выбрать время",
        callback_data=ReminderActionCallback(action="snooze_manual", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=ReminderActionCallback(action="open", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.adjust(1)
    return builder.as_markup()
