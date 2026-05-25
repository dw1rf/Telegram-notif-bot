from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
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
    confirmation_keyboard,
    confirmation_text,
    create_text_keyboard,
    create_text_screen,
    delete_confirm_keyboard,
    delete_confirm_text,
    deleted_keyboard,
    main_menu_text,
    manual_time_keyboard,
    manual_time_screen,
    quick_time_keyboard,
    quick_time_screen,
    reminder_detail_text,
    reminder_manage_keyboard,
    reminders_list_keyboard,
    reminders_list_text,
    repeat_keyboard,
    repeat_screen,
    saved_keyboard,
    snooze_keyboard,
    snooze_text,
)
from app.services.reminder_service import ReminderService
from app.services.scheduler_service import SchedulerService
from app.services.ui_service import answer_error, render_callback, render_state, safe_delete_message
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


class ReminderSnoozeState(StatesGroup):
    waiting_datetime = State()


def _serialize_remind_at(remind_at: datetime) -> str:
    return remind_at.isoformat()


def _deserialize_remind_at(value: str) -> datetime:
    return datetime.fromisoformat(value)


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


def _tomorrow_utc(timezone_name: str) -> datetime:
    now_local = utc_now().astimezone(get_timezone(timezone_name))
    remind_local = (now_local + timedelta(days=1)).replace(second=0, microsecond=0)
    return to_utc(remind_local, timezone_name)


async def _load_owned_reminder(
    session: AsyncSession,
    db_user: User,
    reminder_id: int,
) -> Reminder | None:
    return await ReminderService(session).get_user_reminder(reminder_id, db_user.id)


async def _show_reminders_page(
    callback: CallbackQuery,
    state: FSMContext,
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
    await render_callback(
        callback,
        state,
        reminders_list_text(reminders, db_user.timezone, title),
        reply_markup=reminders_list_keyboard(reminders, scope, page, total_pages),
    )


async def _open_reminder_card(
    callback: CallbackQuery,
    state: FSMContext,
    reminder: Reminder,
    db_user: User,
    scope: str,
    page: int,
) -> None:
    await render_callback(
        callback,
        state,
        reminder_detail_text(reminder, db_user.timezone),
        reply_markup=reminder_manage_keyboard(reminder.id, scope, page),
    )


async def _render_create_repeat(message: Message, state: FSMContext, db_user: User) -> None:
    data = await state.get_data()
    await state.set_state(ReminderCreateState.waiting_repeat)
    await render_state(
        message,
        state,
        repeat_screen(data["text"], _deserialize_remind_at(data["remind_at"]), db_user.timezone),
        reply_markup=repeat_keyboard(),
    )


@router.callback_query(MainMenuCallback.filter(F.action == "create"))
async def start_create_reminder(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ReminderCreateState.waiting_text)
    await render_callback(callback, state, create_text_screen(), reply_markup=create_text_keyboard())


@router.message(ReminderCreateState.waiting_text)
async def receive_reminder_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await render_state(
            message,
            state,
            create_text_screen("Текст не должен быть пустым."),
            reply_markup=create_text_keyboard(),
        )
        await safe_delete_message(message)
        return

    await state.update_data(text=text)
    await state.set_state(ReminderCreateState.waiting_datetime)
    await render_state(message, state, quick_time_screen(text), reply_markup=quick_time_keyboard())
    await safe_delete_message(message)


@router.callback_query(QuickTimeCallback.filter(), ReminderCreateState.waiting_datetime)
async def choose_quick_time(
    callback: CallbackQuery,
    callback_data: QuickTimeCallback,
    state: FSMContext,
    db_user: User,
) -> None:
    if callback_data.value == "manual":
        await state.update_data(manual_time=True)
        await render_callback(callback, state, manual_time_screen(), reply_markup=manual_time_keyboard())
        return

    data = await state.get_data()
    remind_at = _quick_time_to_utc(callback_data.value, db_user.timezone)
    await state.update_data(remind_at=_serialize_remind_at(remind_at), manual_time=False)
    await state.set_state(ReminderCreateState.waiting_repeat)
    await render_callback(
        callback,
        state,
        repeat_screen(data["text"], remind_at, db_user.timezone),
        reply_markup=repeat_keyboard(),
    )


@router.message(ReminderCreateState.waiting_datetime)
async def receive_manual_datetime(message: Message, state: FSMContext, db_user: User) -> None:
    try:
        remind_at = parse_user_datetime((message.text or "").strip(), db_user.timezone)
    except DateParseError as error:
        await render_state(message, state, manual_time_screen(str(error)), reply_markup=manual_time_keyboard())
        await safe_delete_message(message)
        return

    await state.update_data(remind_at=_serialize_remind_at(remind_at), manual_time=False)
    await _render_create_repeat(message, state, db_user)
    await safe_delete_message(message)


@router.callback_query(RepeatChoiceCallback.filter(), ReminderCreateState.waiting_repeat)
async def choose_repeat(
    callback: CallbackQuery,
    callback_data: RepeatChoiceCallback,
    state: FSMContext,
    db_user: User,
) -> None:
    data = await state.get_data()
    remind_at = _deserialize_remind_at(data["remind_at"])
    repeat_type = RepeatType(callback_data.value)
    await state.update_data(repeat_type=repeat_type.value)
    await render_callback(
        callback,
        state,
        confirmation_text(data["text"], remind_at, repeat_type, db_user.timezone),
        reply_markup=confirmation_keyboard(),
    )


@router.callback_query(ConfirmReminderCallback.filter())
async def process_create_control(
    callback: CallbackQuery,
    callback_data: ConfirmReminderCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    scheduler_service: SchedulerService,
) -> None:
    current_state = await state.get_state()
    data = await state.get_data()

    if callback_data.action == "cancel":
        await state.clear()
        await render_callback(callback, state, main_menu_text(), reply_markup=main_menu_keyboard())
        return

    if callback_data.action == "back":
        if current_state == ReminderCreateState.waiting_datetime.state and data.get("manual_time") and "text" in data:
            await state.update_data(manual_time=False)
            await render_callback(callback, state, quick_time_screen(data["text"]), reply_markup=quick_time_keyboard())
            return
        if current_state == ReminderCreateState.waiting_datetime.state:
            await state.set_state(ReminderCreateState.waiting_text)
            await render_callback(callback, state, create_text_screen(), reply_markup=create_text_keyboard())
            return
        if current_state == ReminderCreateState.waiting_repeat.state and "text" in data:
            await state.set_state(ReminderCreateState.waiting_datetime)
            await render_callback(callback, state, quick_time_screen(data["text"]), reply_markup=quick_time_keyboard())
            return
        if data.get("editing_reminder_id"):
            reminder = await _load_owned_reminder(session, db_user, int(data["editing_reminder_id"]))
            if reminder:
                await _open_reminder_card(
                    callback,
                    state,
                    reminder,
                    db_user,
                    str(data.get("editing_scope", "all")),
                    int(data.get("editing_page", 1)),
                )
                return
        await render_callback(callback, state, main_menu_text(), reply_markup=main_menu_keyboard())
        return

    if callback_data.action == "edit_text":
        await state.set_state(ReminderCreateState.waiting_text)
        await render_callback(callback, state, create_text_screen(), reply_markup=create_text_keyboard())
        return

    if callback_data.action == "edit_time":
        if "text" not in data:
            await answer_error(callback, "Создание уже завершено.")
            return
        await state.set_state(ReminderCreateState.waiting_datetime)
        await render_callback(callback, state, quick_time_screen(data["text"]), reply_markup=quick_time_keyboard())
        return

    if callback_data.action == "edit_repeat":
        if {"text", "remind_at"} - data.keys():
            await answer_error(callback, "Создание уже завершено.")
            return
        await state.set_state(ReminderCreateState.waiting_repeat)
        await render_callback(
            callback,
            state,
            repeat_screen(data["text"], _deserialize_remind_at(data["remind_at"]), db_user.timezone),
            reply_markup=repeat_keyboard(),
        )
        return

    if callback_data.action != "save":
        await callback.answer()
        return

    if {"text", "remind_at", "repeat_type"} - data.keys():
        await answer_error(callback, "Создание уже завершено. Начните заново через меню.")
        return

    reminder = await ReminderService(session).create_reminder(
        user_id=db_user.id,
        text=data["text"],
        remind_at=_deserialize_remind_at(data["remind_at"]),
        repeat_type=RepeatType(data["repeat_type"]),
    )
    scheduler_service.schedule_reminder(reminder.id, reminder.remind_at)
    await state.clear()
    await render_callback(callback, state, "✅ Напоминание сохранено", reply_markup=saved_keyboard(), answer_text="Сохранено")


@router.callback_query(MainMenuCallback.filter(F.action == "list"))
async def show_my_reminders(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    await _show_reminders_page(callback, state, session, db_user, page=1, scope="all")


@router.callback_query(MainMenuCallback.filter(F.action == "recurring"))
async def show_recurring_reminders(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    await _show_reminders_page(callback, state, session, db_user, page=1, scope="recurring")


@router.callback_query(ReminderPageCallback.filter())
async def paginate_reminders(
    callback: CallbackQuery,
    callback_data: ReminderPageCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    await _show_reminders_page(callback, state, session, db_user, callback_data.page, callback_data.scope)


@router.callback_query(ReminderActionCallback.filter(F.action == "open"))
async def open_reminder(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await answer_error(callback, "Это не ваше напоминание")
        return
    await _open_reminder_card(callback, state, reminder, db_user, callback_data.scope, callback_data.page)


@router.callback_query(ReminderActionCallback.filter(F.action == "delete_prompt"))
async def prompt_delete_reminder(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await answer_error(callback, "Это не ваше напоминание")
        return
    await render_callback(
        callback,
        state,
        delete_confirm_text(reminder),
        reply_markup=delete_confirm_keyboard(reminder.id, callback_data.scope, callback_data.page),
    )


@router.callback_query(ReminderActionCallback.filter(F.action == "delete_confirm"))
async def delete_reminder(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    scheduler_service: SchedulerService,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await answer_error(callback, "Это не ваше напоминание")
        return

    scheduler_service.remove_job(reminder.id)
    await ReminderService(session).delete_reminder(reminder)
    await render_callback(callback, state, "✅ Напоминание удалено", reply_markup=deleted_keyboard(), answer_text="Удалено")


@router.callback_query(ReminderActionCallback.filter(F.action == "done"))
async def mark_reminder_done(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await answer_error(callback, "Это не ваше напоминание")
        return

    if reminder.repeat_type == RepeatType.NONE and reminder.is_active:
        await ReminderService(session).mark_inactive(reminder)
        text = f"✅ Напоминание выполнено\n\n{reminder.text}"
    else:
        text = (
            "✅ Выполнено\n\n"
            "Следующее напоминание:\n"
            f"{format_user_datetime(reminder.remind_at, db_user.timezone)}"
        )
    await render_callback(callback, state, text, answer_text="Готово")


@router.callback_query(ReminderActionCallback.filter(F.action == "snooze_menu"))
async def show_snooze_menu(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await answer_error(callback, "Это не ваше напоминание")
        return
    await render_callback(
        callback,
        state,
        snooze_text(reminder),
        reply_markup=snooze_keyboard(reminder.id, callback_data.scope, callback_data.page),
    )


@router.callback_query(ReminderActionCallback.filter(F.action.in_({"snooze_10", "snooze_30", "snooze_60", "snooze_tomorrow"})))
async def snooze_reminder(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    scheduler_service: SchedulerService,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await answer_error(callback, "Это не ваше напоминание")
        return

    deltas = {
        "snooze_10": timedelta(minutes=10),
        "snooze_30": timedelta(minutes=30),
        "snooze_60": timedelta(hours=1),
    }
    new_time = _tomorrow_utc(db_user.timezone) if callback_data.action == "snooze_tomorrow" else utc_now() + deltas[callback_data.action]
    await ReminderService(session).activate_with_new_time(reminder, new_time)
    scheduler_service.schedule_reminder(reminder.id, reminder.remind_at)
    await render_callback(
        callback,
        state,
        "✅ Напоминание отложено\n\n"
        f"Новое время: {format_user_datetime(reminder.remind_at, db_user.timezone)}",
        reply_markup=deleted_keyboard(),
        answer_text="Отложено",
    )


@router.callback_query(ReminderActionCallback.filter(F.action.in_({"edit_text", "edit_time", "reschedule_prompt", "snooze_manual"})))
async def prompt_reminder_edit(
    callback: CallbackQuery,
    callback_data: ReminderActionCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    reminder = await _load_owned_reminder(session, db_user, callback_data.reminder_id)
    if reminder is None:
        await answer_error(callback, "Это не ваше напоминание")
        return

    await state.update_data(
        editing_reminder_id=reminder.id,
        editing_scope=callback_data.scope,
        editing_page=callback_data.page,
    )

    if callback_data.action == "edit_text":
        await state.set_state(ReminderEditState.waiting_text)
        await render_callback(callback, state, create_text_screen(), reply_markup=create_text_keyboard())
        return

    if callback_data.action == "snooze_manual":
        await state.set_state(ReminderSnoozeState.waiting_datetime)
    else:
        await state.set_state(ReminderEditState.waiting_datetime)
    await render_callback(callback, state, manual_time_screen(), reply_markup=manual_time_keyboard())


@router.message(ReminderEditState.waiting_text)
async def save_edited_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    text = (message.text or "").strip()
    if not text:
        await render_state(message, state, create_text_screen("Текст не должен быть пустым."), reply_markup=create_text_keyboard())
        await safe_delete_message(message)
        return

    data = await state.get_data()
    reminder = await _load_owned_reminder(session, db_user, int(data["editing_reminder_id"]))
    if reminder is None:
        await render_state(message, state, "Напоминание не найдено.", reply_markup=main_menu_keyboard())
        await state.clear()
        await safe_delete_message(message)
        return

    await ReminderService(session).update_text(reminder, text)
    await render_state(
        message,
        state,
        "✅ Текст обновлён\n\n" + reminder_detail_text(reminder, db_user.timezone),
        reply_markup=reminder_manage_keyboard(reminder.id, str(data.get("editing_scope", "all")), int(data.get("editing_page", 1))),
    )
    await state.clear()
    await safe_delete_message(message)


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
        await render_state(message, state, manual_time_screen(str(error)), reply_markup=manual_time_keyboard())
        await safe_delete_message(message)
        return

    data = await state.get_data()
    reminder = await _load_owned_reminder(session, db_user, int(data["editing_reminder_id"]))
    if reminder is None:
        await render_state(message, state, "Напоминание не найдено.", reply_markup=main_menu_keyboard())
        await state.clear()
        await safe_delete_message(message)
        return

    await ReminderService(session).update_time(reminder, remind_at)
    scheduler_service.schedule_reminder(reminder.id, reminder.remind_at)
    await render_state(
        message,
        state,
        "✅ Время обновлено\n\n" + reminder_detail_text(reminder, db_user.timezone),
        reply_markup=reminder_manage_keyboard(reminder.id, str(data.get("editing_scope", "all")), int(data.get("editing_page", 1))),
    )
    await state.clear()
    await safe_delete_message(message)


@router.message(ReminderSnoozeState.waiting_datetime)
async def save_manual_snooze(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    scheduler_service: SchedulerService,
) -> None:
    try:
        remind_at = parse_user_datetime((message.text or "").strip(), db_user.timezone)
    except DateParseError as error:
        await render_state(message, state, manual_time_screen(str(error)), reply_markup=manual_time_keyboard())
        await safe_delete_message(message)
        return

    data = await state.get_data()
    reminder = await _load_owned_reminder(session, db_user, int(data["editing_reminder_id"]))
    if reminder is None:
        await render_state(message, state, "Напоминание не найдено.", reply_markup=main_menu_keyboard())
        await state.clear()
        await safe_delete_message(message)
        return

    await ReminderService(session).activate_with_new_time(reminder, remind_at)
    scheduler_service.schedule_reminder(reminder.id, reminder.remind_at)
    await render_state(
        message,
        state,
        "✅ Напоминание отложено\n\n"
        f"Новое время: {format_user_datetime(reminder.remind_at, db_user.timezone)}",
        reply_markup=deleted_keyboard(),
    )
    await state.clear()
    await safe_delete_message(message)


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
        await answer_error(callback, "Это не ваше напоминание")
        return

    await state.update_data(
        editing_reminder_id=reminder.id,
        editing_scope=callback_data.scope,
        editing_page=callback_data.page,
    )
    await state.set_state(ReminderEditState.waiting_repeat)
    await render_callback(callback, state, "Выберите новый тип повтора.", reply_markup=repeat_keyboard(include_back=True))


@router.callback_query(RepeatChoiceCallback.filter(), ReminderEditState.waiting_repeat)
async def save_repeat_edit(
    callback: CallbackQuery,
    callback_data: RepeatChoiceCallback,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    data = await state.get_data()
    reminder = await _load_owned_reminder(session, db_user, int(data["editing_reminder_id"]))
    if reminder is None:
        await state.clear()
        await answer_error(callback, "Это не ваше напоминание")
        return

    await ReminderService(session).update_repeat_type(reminder, RepeatType(callback_data.value))
    await state.clear()
    await render_callback(
        callback,
        state,
        "✅ Повтор обновлён\n\n" + reminder_detail_text(reminder, db_user.timezone),
        reply_markup=reminder_manage_keyboard(reminder.id, str(data.get("editing_scope", "all")), int(data.get("editing_page", 1))),
        answer_text="Готово",
    )
