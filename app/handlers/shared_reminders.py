from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import RepeatType, SharedReminderMemberStatus, SharedReminderStatus, User
from app.keyboards.callbacks import MainMenuCallback, RepeatChoiceCallback, SharedJoinCallback, SharedReminderCallback
from app.keyboards.main import main_menu_keyboard
from app.keyboards.reminders import repeat_keyboard
from app.keyboards.shared_reminders import (
    shared_created_text,
    shared_detail_text,
    shared_member_keyboard,
    shared_members_text,
    shared_owner_keyboard,
    shared_reminders_list_keyboard,
    shared_reminders_list_text,
)
from app.services.shared_reminder_service import (
    DESCRIPTION_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    SharedReminderService,
)
from app.utils.datetime_parser import DateParseError, parse_user_datetime
from app.utils.timezone import utc_now


router = Router()


class SharedReminderCreateState(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_datetime = State()
    waiting_repeat = State()


class SharedReminderEditState(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_datetime = State()


def _serialize_remind_at(remind_at: datetime) -> str:
    return remind_at.isoformat()


def _deserialize_remind_at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _repeat_from_choice(value: str) -> RepeatType | None:
    repeat_type = RepeatType(value)
    return None if repeat_type == RepeatType.NONE else repeat_type


async def _invite_link(message: Message | CallbackQuery, token: str) -> str:
    bot = message.bot
    bot_user = await bot.get_me()
    return f"https://t.me/{bot_user.username}?start=join_{token}"


async def _show_user_shared_reminders(message: Message, session: AsyncSession, db_user: User) -> None:
    memberships = await SharedReminderService(session).list_user_reminders(db_user.id)
    await message.answer(
        shared_reminders_list_text(memberships),
        reply_markup=shared_reminders_list_keyboard(memberships),
    )


@router.message(Command("new_shared_reminder"))
@router.message(F.text.casefold().startswith("/общее_напоминание"))
async def start_create_shared_reminder(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SharedReminderCreateState.waiting_title)
    await message.answer("Введите название общего напоминания.")


@router.callback_query(MainMenuCallback.filter(F.action == "create_shared"))
async def start_create_shared_from_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SharedReminderCreateState.waiting_title)
    await callback.message.answer("Введите название общего напоминания.")
    await callback.answer()


@router.message(SharedReminderCreateState.waiting_title)
async def receive_shared_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не должно быть пустым.")
        return
    if len(title) > TITLE_MAX_LENGTH:
        await message.answer(f"Название слишком длинное. Максимум {TITLE_MAX_LENGTH} символов.")
        return

    await state.update_data(title=title)
    await state.set_state(SharedReminderCreateState.waiting_description)
    await message.answer("Введите описание или отправьте `-`, чтобы пропустить.")


@router.message(SharedReminderCreateState.waiting_description)
async def receive_shared_description(message: Message, state: FSMContext) -> None:
    raw_description = (message.text or "").strip()
    description = None if raw_description in {"", "-"} else raw_description
    if description and len(description) > DESCRIPTION_MAX_LENGTH:
        await message.answer(f"Описание слишком длинное. Максимум {DESCRIPTION_MAX_LENGTH} символов.")
        return

    await state.update_data(description=description)
    await state.set_state(SharedReminderCreateState.waiting_datetime)
    await message.answer(
        "Введите дату и время.\n\n"
        "Поддерживаются форматы:\n"
        "25.05.2026 21:00\n"
        "завтра 18:00\n"
        "через 2 часа\n"
        "через 15 минут"
    )


@router.message(SharedReminderCreateState.waiting_datetime)
async def receive_shared_datetime(message: Message, state: FSMContext, db_user: User) -> None:
    try:
        remind_at = parse_user_datetime((message.text or "").strip(), db_user.timezone)
    except DateParseError as error:
        await message.answer(str(error))
        return

    await state.update_data(remind_at=_serialize_remind_at(remind_at))
    await state.set_state(SharedReminderCreateState.waiting_repeat)
    await message.answer("Выберите повторение.", reply_markup=repeat_keyboard())


@router.callback_query(RepeatChoiceCallback.filter(), SharedReminderCreateState.waiting_repeat)
async def save_shared_reminder(
    callback: CallbackQuery,
    callback_data: RepeatChoiceCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    data = await state.get_data()
    service = SharedReminderService(session)
    reminder, token = await service.create_shared_reminder(
        owner=db_user,
        title=data["title"],
        description=data.get("description"),
        remind_at=_deserialize_remind_at(data["remind_at"]),
        repeat_rule=_repeat_from_choice(callback_data.value),
    )
    member_count = await service.active_member_count(reminder.id)
    link = await _invite_link(callback, token)
    await state.clear()
    await callback.message.answer(
        shared_created_text(reminder, member_count, link),
        reply_markup=shared_owner_keyboard(reminder.id),
    )
    await callback.answer()


@router.message(Command("my_shared_reminders"))
@router.message(F.text.casefold().startswith("/мои_общие_напоминания"))
async def show_my_shared_reminders(message: Message, session: AsyncSession, db_user: User) -> None:
    await _show_user_shared_reminders(message, session, db_user)


@router.callback_query(MainMenuCallback.filter(F.action == "shared_list"))
async def show_my_shared_from_menu(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    memberships = await SharedReminderService(session).list_user_reminders(db_user.id)
    await callback.message.edit_text(
        shared_reminders_list_text(memberships),
        reply_markup=shared_reminders_list_keyboard(memberships),
    )
    await callback.answer()


@router.callback_query(SharedJoinCallback.filter())
async def process_join_confirmation(
    callback: CallbackQuery,
    callback_data: SharedJoinCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    if callback_data.action == "cancel":
        await state.clear()
        await callback.message.edit_text("Подключение отменено.", reply_markup=main_menu_keyboard())
        await callback.answer()
        return

    state_data = await state.get_data()
    if state_data.get("pending_shared_join_id") != callback_data.reminder_id:
        await callback.answer("Откройте invite-ссылку заново.", show_alert=True)
        return

    service = SharedReminderService(session)
    reminder = await service.get_reminder(callback_data.reminder_id)
    if reminder is None:
        await callback.answer("Напоминание не найдено.", show_alert=True)
        return
    if reminder.status != SharedReminderStatus.ACTIVE:
        await callback.answer("Это напоминание уже не активно.", show_alert=True)
        return
    if reminder.token_expires_at is not None and reminder.token_expires_at <= utc_now():
        await callback.answer("Срок действия invite-токена истёк.", show_alert=True)
        return
    if reminder.invite_token_hash != state_data.get("pending_shared_join_hash"):
        await callback.answer("Invite-токен уже изменён. Откройте новую ссылку.", show_alert=True)
        return

    joined, status = await service.join_reminder(reminder, db_user)
    await state.clear()
    if status == "removed":
        await callback.message.edit_text("Владелец удалил вас из этого напоминания.")
    elif status == "already":
        await callback.message.edit_text("Вы уже подключены к этому общему напоминанию.")
    else:
        await callback.message.edit_text("Вы подключены к общему напоминанию.")
    await callback.answer("Готово" if joined else None)


@router.callback_query(SharedReminderCallback.filter(F.action == "open"))
async def open_shared_reminder(
    callback: CallbackQuery,
    callback_data: SharedReminderCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    service = SharedReminderService(session)
    reminder = await service.get_reminder(callback_data.reminder_id)
    member = await service.get_member(callback_data.reminder_id, db_user.id)
    if reminder is None or member is None:
        await callback.answer("Напоминание не найдено.", show_alert=True)
        return

    member_count = await service.active_member_count(reminder.id)
    keyboard = (
        shared_owner_keyboard(reminder.id)
        if reminder.owner_user_id == db_user.id
        else shared_member_keyboard(reminder.id, member.status == SharedReminderMemberStatus.MUTED)
    )
    await callback.message.edit_text(shared_detail_text(reminder, member_count), reply_markup=keyboard)
    await callback.answer()


@router.callback_query(SharedReminderCallback.filter(F.action == "members"))
async def show_shared_members(
    callback: CallbackQuery,
    callback_data: SharedReminderCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    service = SharedReminderService(session)
    reminder = await service.ensure_owner(callback_data.reminder_id, db_user.id)
    if reminder is None:
        await callback.answer("Только владелец может смотреть участников.", show_alert=True)
        return

    members = await service.list_members(reminder.id)
    await callback.message.answer(shared_members_text(members), reply_markup=shared_owner_keyboard(reminder.id))
    await callback.answer()


@router.callback_query(SharedReminderCallback.filter(F.action.in_({"edit_title", "edit_desc", "edit_time"})))
async def prompt_shared_edit(
    callback: CallbackQuery,
    callback_data: SharedReminderCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    reminder = await SharedReminderService(session).ensure_owner(callback_data.reminder_id, db_user.id)
    if reminder is None:
        await callback.answer("Только владелец может редактировать напоминание.", show_alert=True)
        return

    await state.update_data(editing_shared_reminder_id=reminder.id)
    if callback_data.action == "edit_title":
        await state.set_state(SharedReminderEditState.waiting_title)
        await callback.message.answer("Введите новое название.")
    elif callback_data.action == "edit_desc":
        await state.set_state(SharedReminderEditState.waiting_description)
        await callback.message.answer("Введите новое описание или `-`, чтобы очистить.")
    else:
        await state.set_state(SharedReminderEditState.waiting_datetime)
        await callback.message.answer("Введите новую дату и время.")
    await callback.answer()


@router.message(SharedReminderEditState.waiting_title)
async def save_shared_title(message: Message, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не должно быть пустым.")
        return
    if len(title) > TITLE_MAX_LENGTH:
        await message.answer(f"Название слишком длинное. Максимум {TITLE_MAX_LENGTH} символов.")
        return

    data = await state.get_data()
    service = SharedReminderService(session)
    reminder = await service.ensure_owner(int(data["editing_shared_reminder_id"]), db_user.id)
    if reminder is None:
        await state.clear()
        await message.answer("Напоминание не найдено.")
        return

    await service.update_title(reminder, title)
    member_count = await service.active_member_count(reminder.id)
    await state.clear()
    await message.answer("Название обновлено.\n\n" + shared_detail_text(reminder, member_count), reply_markup=shared_owner_keyboard(reminder.id))


@router.message(SharedReminderEditState.waiting_description)
async def save_shared_description(message: Message, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    raw_description = (message.text or "").strip()
    description = None if raw_description in {"", "-"} else raw_description
    if description and len(description) > DESCRIPTION_MAX_LENGTH:
        await message.answer(f"Описание слишком длинное. Максимум {DESCRIPTION_MAX_LENGTH} символов.")
        return

    data = await state.get_data()
    service = SharedReminderService(session)
    reminder = await service.ensure_owner(int(data["editing_shared_reminder_id"]), db_user.id)
    if reminder is None:
        await state.clear()
        await message.answer("Напоминание не найдено.")
        return

    await service.update_description(reminder, description)
    member_count = await service.active_member_count(reminder.id)
    await state.clear()
    await message.answer("Описание обновлено.\n\n" + shared_detail_text(reminder, member_count), reply_markup=shared_owner_keyboard(reminder.id))


@router.message(SharedReminderEditState.waiting_datetime)
async def save_shared_datetime(message: Message, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    try:
        remind_at = parse_user_datetime((message.text or "").strip(), db_user.timezone)
    except DateParseError as error:
        await message.answer(str(error))
        return

    data = await state.get_data()
    service = SharedReminderService(session)
    reminder = await service.ensure_owner(int(data["editing_shared_reminder_id"]), db_user.id)
    if reminder is None:
        await state.clear()
        await message.answer("Напоминание не найдено.")
        return

    await service.update_time(reminder, remind_at)
    member_count = await service.active_member_count(reminder.id)
    await state.clear()
    await message.answer("Время обновлено.\n\n" + shared_detail_text(reminder, member_count), reply_markup=shared_owner_keyboard(reminder.id))


@router.callback_query(SharedReminderCallback.filter(F.action.in_({"renew_token", "disable_token", "cancel_reminder"})))
async def process_owner_shared_action(
    callback: CallbackQuery,
    callback_data: SharedReminderCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    service = SharedReminderService(session)
    reminder = await service.ensure_owner(callback_data.reminder_id, db_user.id)
    if reminder is None:
        await callback.answer("Только владелец может управлять напоминанием.", show_alert=True)
        return

    if callback_data.action == "renew_token":
        token = await service.renew_token(reminder)
        link = await _invite_link(callback, token)
        await callback.message.answer(
            "Новый invite-токен создан. Старый токен больше не работает.\n\n"
            f"Ссылка для подключения:\n{link}",
            reply_markup=shared_owner_keyboard(reminder.id),
        )
        await callback.answer("Токен обновлён")
        return

    if callback_data.action == "disable_token":
        await service.disable_token(reminder)
        await callback.answer("Invite-токен отключён.")
        await callback.message.answer("Invite-токен отключён.", reply_markup=shared_owner_keyboard(reminder.id))
        return

    await service.cancel(reminder)
    await callback.message.edit_text("Общее напоминание отменено.")
    await callback.answer("Отменено")


@router.callback_query(SharedReminderCallback.filter(F.action.in_({"mute", "unmute", "leave", "done"})))
async def process_member_shared_action(
    callback: CallbackQuery,
    callback_data: SharedReminderCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    service = SharedReminderService(session)

    if callback_data.action == "done":
        await callback.message.edit_reply_markup()
        await callback.answer("Отмечено.")
        return

    status = {
        "mute": SharedReminderMemberStatus.MUTED,
        "unmute": SharedReminderMemberStatus.ACTIVE,
        "leave": SharedReminderMemberStatus.LEFT,
    }[callback_data.action]
    changed = await service.set_member_status(callback_data.reminder_id, db_user.id, status)
    if not changed:
        await callback.answer("Действие недоступно.", show_alert=True)
        return

    messages = {
        "mute": "Уведомления по этому напоминанию отключены.",
        "unmute": "Уведомления снова включены.",
        "leave": "Вы вышли из общего напоминания.",
    }
    await callback.message.edit_text(messages[callback_data.action])
    await callback.answer("Готово")
