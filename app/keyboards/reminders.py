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


def quick_time_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Через 10 минут", callback_data=QuickTimeCallback(value="10m"))
    builder.button(text="Через 30 минут", callback_data=QuickTimeCallback(value="30m"))
    builder.button(text="Через 1 час", callback_data=QuickTimeCallback(value="1h"))
    builder.button(text="Сегодня вечером", callback_data=QuickTimeCallback(value="evening"))
    builder.button(text="Завтра утром", callback_data=QuickTimeCallback(value="tomorrow_morning"))
    builder.button(text="Ввести вручную", callback_data=QuickTimeCallback(value="manual"))
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def repeat_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Не повторять", callback_data=RepeatChoiceCallback(value=RepeatType.NONE.value))
    builder.button(text="Каждый день", callback_data=RepeatChoiceCallback(value=RepeatType.DAILY.value))
    builder.button(text="Каждую неделю", callback_data=RepeatChoiceCallback(value=RepeatType.WEEKLY.value))
    builder.button(text="Каждый месяц", callback_data=RepeatChoiceCallback(value=RepeatType.MONTHLY.value))
    builder.adjust(1)
    return builder.as_markup()


def confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сохранить", callback_data=ConfirmReminderCallback(action="save"))
    builder.button(text="✏️ Изменить текст", callback_data=ConfirmReminderCallback(action="edit_text"))
    builder.button(text="🕒 Изменить время", callback_data=ConfirmReminderCallback(action="edit_time"))
    builder.button(text="🔁 Изменить повтор", callback_data=ConfirmReminderCallback(action="edit_repeat"))
    builder.button(text="❌ Отмена", callback_data=ConfirmReminderCallback(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def reminder_detail_text(reminder: Reminder, timezone_name: str) -> str:
    return (
        f"Текст: {reminder.text}\n"
        f"Время: {format_user_datetime(reminder.remind_at, timezone_name)}\n"
        f"Повтор: {REPEAT_LABELS[reminder.repeat_type]}"
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

    for index, reminder in enumerate(reminders, start=1):
        builder.row(
            InlineKeyboardButton(
                text=f"✏️ {index}",
                callback_data=ReminderActionCallback(
                    action="open",
                    reminder_id=reminder.id,
                    scope=scope,
                    page=page,
                ).pack(),
            ),
            InlineKeyboardButton(
                text=f"🗑 {index}",
                callback_data=ReminderActionCallback(
                    action="delete",
                    reminder_id=reminder.id,
                    scope=scope,
                    page=page,
                ).pack(),
            ),
            InlineKeyboardButton(
                text=f"⏰ {index}",
                callback_data=ReminderActionCallback(
                    action="snooze_10",
                    reminder_id=reminder.id,
                    scope=scope,
                    page=page,
                ).pack(),
            ),
        )

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
            text="⬅️ Назад",
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
        text="⏰ Отложить на 10 минут",
        callback_data=ReminderActionCallback(action="snooze_10", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="🕐 Отложить на 1 час",
        callback_data=ReminderActionCallback(action="snooze_60", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="📅 Перенести",
        callback_data=ReminderActionCallback(action="reschedule_prompt", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="🗑 Удалить",
        callback_data=ReminderActionCallback(action="delete", reminder_id=reminder_id, scope=scope, page=page),
    )
    builder.button(
        text="⬅️ К списку",
        callback_data=ReminderPageCallback(scope=scope, page=page),
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
        callback_data=ReminderActionCallback(action="reschedule_prompt", reminder_id=reminder_id, scope="fired"),
    )
    builder.button(
        text="🗑 Удалить",
        callback_data=ReminderActionCallback(action="delete", reminder_id=reminder_id, scope="fired"),
    )
    builder.adjust(1)
    return builder.as_markup()
