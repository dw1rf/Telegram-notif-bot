from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models import RepeatType, SharedReminder, SharedReminderMember, SharedReminderMemberStatus
from app.keyboards.callbacks import MainMenuCallback, SharedJoinCallback, SharedReminderCallback
from app.keyboards.reminders import REPEAT_LABELS
from app.utils.timezone import format_user_datetime


def repeat_label(repeat_rule: RepeatType | None) -> str:
    return REPEAT_LABELS[repeat_rule or RepeatType.NONE]


def shared_reminder_card_text(
    reminder: SharedReminder,
    member_count: int,
    timezone_name: str | None = None,
) -> str:
    timezone_name = timezone_name or reminder.timezone
    description = reminder.description or "не указано"
    return (
        "Вы хотите подключиться к общему напоминанию?\n\n"
        f"Название: {reminder.title}\n"
        f"Описание: {description}\n"
        f"Время: {format_user_datetime(reminder.remind_at, timezone_name)}\n"
        f"Повтор: {repeat_label(reminder.repeat_rule)}\n"
        f"Участников: {member_count}"
    )


def shared_created_text(
    reminder: SharedReminder,
    member_count: int,
    invite_link: str,
) -> str:
    return (
        "🔔 Общее напоминание создано\n\n"
        f"Название: {reminder.title}\n"
        f"Время: {format_user_datetime(reminder.remind_at, reminder.timezone)}\n"
        f"Участников: {member_count}\n\n"
        "Ссылка для подключения:\n"
        f"{invite_link}"
    )


def shared_detail_text(reminder: SharedReminder, member_count: int) -> str:
    description = reminder.description or "не указано"
    return (
        "🔔 Общее напоминание\n\n"
        f"Название: {reminder.title}\n"
        f"Описание: {description}\n"
        f"Время: {format_user_datetime(reminder.remind_at, reminder.timezone)}\n"
        f"Повтор: {repeat_label(reminder.repeat_rule)}\n"
        f"Статус: {reminder.status.value}\n"
        f"Участников: {member_count}"
    )


def shared_delivery_text(reminder: SharedReminder) -> str:
    description = reminder.description or "не указано"
    return (
        "🔔 Общее напоминание\n\n"
        f"Название: {reminder.title}\n"
        f"Описание: {description}\n"
        f"Время: {format_user_datetime(reminder.remind_at, reminder.timezone)}"
    )


def shared_join_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подключиться", callback_data=SharedJoinCallback(action="confirm", reminder_id=reminder_id))
    builder.button(text="❌ Отмена", callback_data=SharedJoinCallback(action="cancel", reminder_id=reminder_id))
    builder.adjust(1)
    return builder.as_markup()


def shared_owner_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Участники", callback_data=SharedReminderCallback(action="members", reminder_id=reminder_id))
    builder.button(text="✏️ Название", callback_data=SharedReminderCallback(action="edit_title", reminder_id=reminder_id))
    builder.button(text="📝 Описание", callback_data=SharedReminderCallback(action="edit_desc", reminder_id=reminder_id))
    builder.button(text="🕒 Дата и время", callback_data=SharedReminderCallback(action="edit_time", reminder_id=reminder_id))
    builder.button(text="🔁 Новый токен", callback_data=SharedReminderCallback(action="renew_token", reminder_id=reminder_id))
    builder.button(text="🔒 Отключить токен", callback_data=SharedReminderCallback(action="disable_token", reminder_id=reminder_id))
    builder.button(text="❌ Отменить", callback_data=SharedReminderCallback(action="cancel_reminder", reminder_id=reminder_id))
    builder.adjust(1)
    return builder.as_markup()


def shared_delivery_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выполнено", callback_data=SharedReminderCallback(action="done", reminder_id=reminder_id))
    builder.button(text="🔕 Отключить для меня", callback_data=SharedReminderCallback(action="mute", reminder_id=reminder_id))
    builder.button(text="🚪 Выйти из напоминания", callback_data=SharedReminderCallback(action="leave", reminder_id=reminder_id))
    builder.adjust(1)
    return builder.as_markup()


def shared_member_keyboard(reminder_id: int, is_muted: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_muted:
        builder.button(text="🔔 Включить уведомления", callback_data=SharedReminderCallback(action="unmute", reminder_id=reminder_id))
    else:
        builder.button(text="🔕 Отключить уведомления", callback_data=SharedReminderCallback(action="mute", reminder_id=reminder_id))
    builder.button(text="🚪 Выйти", callback_data=SharedReminderCallback(action="leave", reminder_id=reminder_id))
    builder.adjust(1)
    return builder.as_markup()


def shared_reminders_list_text(memberships: list[SharedReminderMember]) -> str:
    if not memberships:
        return "👥 Мои общие напоминания\n\nСписок пуст."

    lines = ["👥 Мои общие напоминания", ""]
    for index, membership in enumerate(memberships, start=1):
        reminder = membership.reminder
        lines.append(f"{index}. {reminder.title}")
        lines.append(f"   {format_user_datetime(reminder.remind_at, reminder.timezone)}")
        lines.append(f"   Статус участия: {membership.status.value}")
        lines.append("")
    return "\n".join(lines).strip()


def shared_reminders_list_keyboard(memberships: list[SharedReminderMember]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, membership in enumerate(memberships, start=1):
        builder.row(
            InlineKeyboardButton(
                text=f"Открыть {index}",
                callback_data=SharedReminderCallback(action="open", reminder_id=membership.reminder_id).pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=MainMenuCallback(action="back_main").pack(),
        )
    )
    return builder.as_markup()


def shared_members_text(members: list[SharedReminderMember]) -> str:
    if not members:
        return "Участников пока нет."

    lines = ["👥 Участники", ""]
    for member in members:
        name = member.first_name or member.username or f"user_id={member.user_id}"
        muted = " muted" if member.status == SharedReminderMemberStatus.MUTED else ""
        lines.append(f"- {name}: {member.role.value}, {member.status.value}{muted}")
    return "\n".join(lines)
