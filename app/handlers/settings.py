from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.keyboards.callbacks import MainMenuCallback, SettingsCallback
from app.keyboards.settings import settings_keyboard
from app.services.reminder_service import ReminderService
from app.services.scheduler_service import SchedulerService
from app.services.user_service import UserService
from app.utils.timezone import is_valid_timezone


router = Router()


class SettingsState(StatesGroup):
    waiting_timezone = State()


@router.callback_query(SettingsCallback.filter(F.action == "timezone"))
async def prompt_timezone(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    await state.set_state(SettingsState.waiting_timezone)
    await callback.message.answer(
        f"Текущий часовой пояс: {db_user.timezone}\n\nВведите новый часовой пояс, например Europe/Moscow."
    )
    await callback.answer()


@router.message(SettingsState.waiting_timezone)
async def update_timezone(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    timezone_name = (message.text or "").strip()
    if not is_valid_timezone(timezone_name):
        await message.answer("Не удалось распознать часовой пояс. Пример: Europe/Bucharest.")
        return

    await UserService(session).update_timezone(db_user, timezone_name)
    await state.clear()
    await message.answer(
        f"Часовой пояс обновлен: {timezone_name}",
        reply_markup=settings_keyboard(),
    )


@router.callback_query(SettingsCallback.filter(F.action == "test"))
async def create_test_reminder(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    scheduler_service: SchedulerService,
) -> None:
    reminder = await ReminderService(session).create_test_reminder(db_user.id)
    scheduler_service.schedule_reminder(reminder.id, reminder.remind_at)
    await callback.message.answer("Тестовое напоминание запланировано на ближайшую минуту.")
    await callback.answer()


@router.callback_query(MainMenuCallback.filter(F.action == "settings"))
async def open_settings(callback: CallbackQuery, db_user: User) -> None:
    await callback.message.edit_text(
        f"⚙️ Настройки\n\nЧасовой пояс: {db_user.timezone}",
        reply_markup=settings_keyboard(),
    )
    await callback.answer()
