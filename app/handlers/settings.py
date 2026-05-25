from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.keyboards.callbacks import MainMenuCallback, SettingsCallback
from app.keyboards.settings import settings_keyboard, settings_text, timezone_prompt_keyboard, timezone_prompt_text
from app.services.reminder_service import ReminderService
from app.services.scheduler_service import SchedulerService
from app.services.ui_service import render_callback, render_state, safe_delete_message
from app.services.user_service import UserService
from app.utils.timezone import is_valid_timezone


router = Router()


class SettingsState(StatesGroup):
    waiting_timezone = State()


@router.callback_query(SettingsCallback.filter(F.action == "timezone"))
async def prompt_timezone(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    await state.set_state(SettingsState.waiting_timezone)
    await render_callback(
        callback,
        state,
        timezone_prompt_text(db_user.timezone),
        reply_markup=timezone_prompt_keyboard(),
    )


@router.message(SettingsState.waiting_timezone)
async def update_timezone(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    timezone_name = (message.text or "").strip()
    if not is_valid_timezone(timezone_name):
        await render_state(
            message,
            state,
            timezone_prompt_text(db_user.timezone, "Не удалось распознать часовой пояс. Пример: Europe/Bucharest."),
            reply_markup=timezone_prompt_keyboard(),
        )
        await safe_delete_message(message)
        return

    await UserService(session).update_timezone(db_user, timezone_name)
    await render_state(
        message,
        state,
        settings_text(timezone_name, "Часовой пояс обновлён."),
        reply_markup=settings_keyboard(),
    )
    await state.clear()
    await safe_delete_message(message)


@router.callback_query(SettingsCallback.filter(F.action == "test"))
async def create_test_reminder(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    scheduler_service: SchedulerService,
) -> None:
    reminder = await ReminderService(session).create_test_reminder(db_user.id)
    scheduler_service.schedule_reminder(reminder.id, reminder.remind_at)
    await render_callback(
        callback,
        state,
        settings_text(db_user.timezone, "Тестовое напоминание запланировано на ближайшую минуту."),
        reply_markup=settings_keyboard(),
        answer_text="Запланировано",
    )


@router.callback_query(MainMenuCallback.filter(F.action == "settings"))
async def open_settings(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    await render_callback(
        callback,
        state,
        settings_text(db_user.timezone),
        reply_markup=settings_keyboard(),
    )
