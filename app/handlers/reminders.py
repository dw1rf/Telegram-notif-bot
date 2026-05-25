from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Reminder, RepeatType, User
from app.keyboards.callbacks import (
    ConfirmReminderCallback,
    MainMenuCallback,
    QuickTimeCallback,
    ReminderActionCallback,
    ReminderPageCallback,
    RepeatChoiceCallback,
)
from app.keyboards.main import main_menu_keyboard
from app.keyboards.reminders import (
    REPEAT_LABELS,
    confirmation_keyboard,
    quick_time_keyboard,
    reminder_detail_text,
    reminder_manage_keyboard,
    reminders_list_keyboard,
    reminders_list_text,
    repeat_keyboard,
)
from app.services.reminder_service import ReminderService
from app.services.scheduler_service import SchedulerService
from app.utils.datetime_parser import DateParseError, parse_user_datetime
from app.utils.timezone import format_user_datetime, get_timezone, to_utc, utc_now


router = Router()
PAGE_SIZE = 5


class ReminderCreateState(StatesGroup):
    waiting_text = State()
    waiting_datetime = State()
    waiting_repeat = State()


class ReminderEditState(StatesGroup):
    waiting_text = State()
    waiting_datetime = State()
    waiting_repeat = State()


def _serialize_remind_at(remind_at: datetime) -> str:
    return remind_at.isoformat()


def _deserialize_remind_at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _confirmation_text(
    text: str,
    remind_at: datetime,
    repeat_type: RepeatType,
    timezone_name: str,
) -> str:
    return (
        "Проверьте напоминание:\n\n"
        f"Текст: {text}\n"
        f"Время: {format_user_datetime(remind_at, timezone_name)}\n"
        f"Повтор: {REPEAT_LABELS[repeat_type]}"
    )


def _quick_time_to_utc(value: str, timezone_name: str) -> datetime:
    now_local = utc_now().astimezone(get_timezone(timezone_name))

    if value == "10m":
        return (utc_now() + timedelta(minutes=10)).replace(second=0, microsecond=0)
    if value == "30m":
        return (utc_now() + timedelta(minutes=30)).replace(second=0, microsecond=0)
    if value == "1h":
        return (utc_now() + timedelta(hours=1)).replace(second=0, microsecond=0)
    if value == "evening":
        remind_local = now_local.replace(hour=19, minute=0, second=0, microsecond=0)
        if remind_local <= now_local:
            remind_local += timedelta(days=1)
        return to_utc(remind_local, timezone_name)

    remind_local = (now_local + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return to_utc(remind_local, timezone_name)


async def _load_owned_reminder(
    session: AsyncSession,
    db_user: User,
    reminder_id: int,
) -> Reminder | None:
    return await ReminderService(session).get_user_reminder(reminder_id, db_user.id)


async def _show_reminders_page(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    page: int,
    scope: str,
) -> None:
    recurring_only = scope == "recurring"
    reminders, total_pages, _ = await ReminderService(session).get_user_reminders(
        user_id=db_user.id,
        page=page,
        page_size=PAGE_SIZE,
        recurring_only=recurring_only,
    )
    page = min(max(page, 1), total_pages)
    title = "🔁 Повторяющиеся напоминания" if recurring_only else "📋 Мои напоминания"
    await callback.message.edit_text(
        reminders_list_text(reminders, db_user.timezone, title),
        reply_markup=reminders_list_keyboard(reminders, scope, page, total_pages),
    )


def _editing_keyboard(reminder_id: int, state_data: dict[str, int | str]) -> InlineKeyboardMarkup:
    return reminder_manage_keyboard(
        reminder_id=reminder_id,
        scope=str(state_data.get("editing_scope", "all")),
        page=int(state_data.get("editing_page", 1)),
    )


@router.callback_query(MainMenuCallback.filter(F.action == "create"))
async def start_create_reminder(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ReminderCreateState.waiting_text)
    await callback.message.answer("Что напомнить?")
    await callback.answer()


@router.message(ReminderCreateState.waiting_text)
async def receive_reminder_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст напоминания не должен быть пустым.")
        return

    await state.update_data(text=text)
    await state.set_state(ReminderCreateState.waiting_datetime)
    await message.answer("Когда напомнить?", reply_markup=quick_time_keyboard())


@router.callback_query(QuickTimeCallback.filter(), ReminderCreateState.waiting_datetime)
async def choose_quick_time(
    callback: CallbackQuery,
    callback_data: QuickTimeCallback,
    state: FSMContext,
    db_user: User,
) -> None:
    if callback_data.value == "manual":
        await callback.message.answer(
            "Введите время вручную.\n\nПоддерживаются:\n25.05.2026 21:00\nзавтра 18:00\nчерез 2 часа\nчерез 15 минут"
        )
        await callback.answer()
        return

    remind_at = _quick_time_to_utc(callback_data.value, db_user.timezone)
    await state.update_data(remind_at=_serialize_remind_at(remind_at))
    await state.set_state(ReminderCreateState.waiting_repeat)
    await callback.message.answer("Повторять?", reply_markup=repeat_keyboard())
    await callback.answer()


@router.message(ReminderCreateState.waiting_datetime)
async def receive_manual_datetime(message: Message, state: FSMContext, db_user: User) -> None:
    try:
        remind_at = parse_user_datetime((message.text or "").strip(), db_user.timezone)
    except DateParseError as error:
        await message.answer(str(error))
        return

    await state.update_data(remind_at=_serialize_remind_at(remind_at))
    await state.set_state(ReminderCreateState.waiting_repeat)
    await message.answer("Повторять?", reply_markup=repeat_keyboard())


@router.callback_query(RepeatChoiceCallback.filter(), ReminderCreateState.waiting_repeat)
async def choose_repeat(
    callback: CallbackQuery,
    callback_data: RepeatChoiceCallback,
    state: FSMContext,
    db_user: User,
) -> None:
    state_data = await state.get_data()
    remind_at = _deserialize_remind_at(state_data["remind_at"])
    repeat_type = RepeatType(callback_data.value)
    await state.update_data(repeat_type=repeat_type.value)
    await callback.message.answer(
        _confirmation_text(state_data["text"], remind_at, repeat_type, db_user.timezone),
        reply_markup=confirmation_keyboard(),
    )
    await callback.answer()


@router.callback_query(ConfirmReminderCallback.filter())
async def confirm_reminder(
    callback: CallbackQuery,
    callback_data: ConfirmReminderCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    scheduler_service: SchedulerService,
) -> None:
    data = await state.get_data()

    if callback_data.action == "save" and {"text", "remind_at", "repeat_type"} - data.keys():
        await callback.answer("Сценарий уже завершен. Начните заново через меню.", show_alert=True)
        return

    if callback_data.action == "cancel":
        await state.clear()
        await callback.message.answer("Создание напоминания отменено.", reply_markup=main_menu_keyboard())
        await callback.answer()
        return

    if callback_data.action == "edit_text":
        await state.set_state(ReminderCreateState.waiting_text)
        await callback.message.answer("Введите новый текст напоминания.")
        await callback.answer()
        return

    if callback_data.action == "edit_time":
        await state.set_state(ReminderCreateState.waiting_datetime)
        await callback.message.answer("Введите новое время.", reply_markup=quick_time_keyboard())
        await callback.answer()
        return

    if callback_data.action == "edit_repeat":
        await state.set_state(ReminderCreateState.waiting_repeat)
        await callback.message.answer("Выберите новый повтор.", reply_markup=repeat_keyboard())
        await callback.answer()
        return

    reminder = await ReminderService(session).create_reminder(
        user_id=db_user.id,
        text=data["text"],
        remind_at=_deserialize_remind_at(data["remind_at"]),
        repeat_type=RepeatType(data["repeat_type"]),
    )
    scheduler_service.schedule_reminder(reminder.id, reminder.remind_at)
    await state.clear()
    await callback.message.answer("Напоминание сохранено.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(MainMenuCallback.filter(F.action == "list"))
async def show_my_reminders(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    await _show_reminders_page(callback, session, db_user, page=1, scope="all")
    await callback.answer()


@router.callback_query(MainMenuCallback.filter(F.action == "recurring"))
async def show_recurring_reminders(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    await _show_reminders_page(callback, session, db_user, page=1, scope="recurring")
    await callback.answer()


@router.callback_query(ReminderPageCallback.filter())
async def paginate_reminders(
    callback: CallbackQuery,
    callback_data: ReminderPageCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    await _show_reminders_page(callback, session, db_user, callback_data.page, callback_data.scope)
    await callback.answer()


@router.callback_query(ReminderActionCallback.filter(F.action == "open"))
async def open_reminder(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await callback.answer("Напоминание не найдено.", show_alert=True)
        return

    await callback.message.edit_text(
        reminder_detail_text(reminder, db_user.timezone),
        reply_markup=reminder_manage_keyboard(reminder.id, callback_data.scope, callback_data.page),
    )
    await callback.answer()


@router.callback_query(ReminderActionCallback.filter(F.action.in_({"delete", "done", "snooze_10", "snooze_60"})))
async def process_reminder_action(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    session: AsyncSession,
    db_user: User,
    scheduler_service: SchedulerService,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await callback.answer("Напоминание уже недоступно.", show_alert=True)
        return

    service = ReminderService(session)

    if callback_data.action == "delete":
        scheduler_service.remove_job(reminder.id)
        await service.delete_reminder(reminder)
        await callback.answer("Напоминание удалено.")
        if callback_data.scope in {"all", "recurring"}:
            await _show_reminders_page(callback, session, db_user, callback_data.page, callback_data.scope)
        else:
            await callback.message.edit_reply_markup()
        return

    if callback_data.action == "done":
        if reminder.repeat_type == RepeatType.NONE and reminder.is_active:
            await service.mark_inactive(reminder)
        await callback.message.edit_reply_markup()
        await callback.answer("Отмечено.")
        return

    new_time = utc_now() + (timedelta(minutes=10) if callback_data.action == "snooze_10" else timedelta(hours=1))
    await service.activate_with_new_time(reminder, new_time)
    scheduler_service.schedule_reminder(reminder.id, reminder.remind_at)
    await callback.answer("Напоминание отложено.")
    if callback_data.scope in {"all", "recurring"}:
        await _show_reminders_page(callback, session, db_user, callback_data.page, callback_data.scope)
    else:
        await callback.message.edit_reply_markup()


@router.callback_query(ReminderActionCallback.filter(F.action.in_({"edit_text", "edit_time", "reschedule_prompt"})))
async def prompt_reminder_edit(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await callback.answer("Напоминание не найдено.", show_alert=True)
        return

    await state.update_data(
        editing_reminder_id=reminder.id,
        editing_scope=callback_data.scope,
        editing_page=callback_data.page,
    )

    if callback_data.action == "edit_text":
        await state.set_state(ReminderEditState.waiting_text)
        await callback.message.answer("Введите новый текст напоминания.")
    else:
        await state.set_state(ReminderEditState.waiting_datetime)
        await callback.message.answer(
            "Введите новое время.\n\nПоддерживаются:\n25.05.2026 21:00\nзавтра 18:00\nчерез 2 часа\nчерез 15 минут"
        )
    await callback.answer()


@router.message(ReminderEditState.waiting_text)
async def save_edited_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    state_data = await state.get_data()
    reminder = await _load_owned_reminder(session, db_user, int(state_data["editing_reminder_id"]))
    if reminder is None:
        await state.clear()
        await message.answer("Напоминание не найдено.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не должен быть пустым.")
        return

    await ReminderService(session).update_text(reminder, text)
    await state.clear()
    await message.answer(
        "Текст обновлен.\n\n" + reminder_detail_text(reminder, db_user.timezone),
        reply_markup=_editing_keyboard(reminder.id, state_data),
    )


@router.message(ReminderEditState.waiting_datetime)
async def save_edited_datetime(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    scheduler_service: SchedulerService,
) -> None:
    try:
        remind_at = parse_user_datetime((message.text or "").strip(), db_user.timezone)
    except DateParseError as error:
        await message.answer(str(error))
        return

    state_data = await state.get_data()
    reminder = await _load_owned_reminder(session, db_user, int(state_data["editing_reminder_id"]))
    if reminder is None:
        await state.clear()
        await message.answer("Напоминание не найдено.")
        return

    await ReminderService(session).update_time(reminder, remind_at)
    scheduler_service.schedule_reminder(reminder.id, reminder.remind_at)
    await state.clear()
    await message.answer(
        "Время обновлено.\n\n" + reminder_detail_text(reminder, db_user.timezone),
        reply_markup=_editing_keyboard(reminder.id, state_data),
    )


@router.callback_query(ReminderActionCallback.filter(F.action == "edit_repeat"))
async def prompt_repeat_edit(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await callback.answer("Напоминание не найдено.", show_alert=True)
        return

    await state.update_data(
        editing_reminder_id=reminder.id,
        editing_scope=callback_data.scope,
        editing_page=callback_data.page,
    )
    await state.set_state(ReminderEditState.waiting_repeat)
    await callback.message.answer("Выберите новый тип повтора.", reply_markup=repeat_keyboard())
    await callback.answer()


@router.callback_query(RepeatChoiceCallback.filter(), ReminderEditState.waiting_repeat)
async def save_repeat_edit(
    callback: CallbackQuery,
    callback_data: RepeatChoiceCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    state_data = await state.get_data()
    reminder = await _load_owned_reminder(session, db_user, int(state_data["editing_reminder_id"]))
    if reminder is None:
        await state.clear()
        await callback.answer("Напоминание не найдено.", show_alert=True)
        return

    await ReminderService(session).update_repeat_type(reminder, RepeatType(callback_data.value))
    await state.clear()
    await callback.message.answer(
        "Повтор обновлен.\n\n" + reminder_detail_text(reminder, db_user.timezone),
        reply_markup=_editing_keyboard(reminder.id, state_data),
    )
    await callback.answer()
