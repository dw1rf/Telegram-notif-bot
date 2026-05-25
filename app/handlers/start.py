from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.keyboards.callbacks import MainMenuCallback
from app.keyboards.main import main_menu_keyboard
from app.keyboards.reminders import main_menu_text
from app.keyboards.shared_reminders import shared_join_keyboard, shared_reminder_card_text
from app.services.shared_reminder_service import SharedReminderService, hash_invite_token
from app.services.ui_service import remember_ui_message, render_callback


router = Router()


@router.message(CommandStart())
async def command_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    payload = command.args or ""
    if payload.startswith("join_"):
        token = payload.removeprefix("join_")
        service = SharedReminderService(session)
        reminder = await service.get_active_by_token(token)
        if reminder is None:
            await message.answer("Invite-ссылка недействительна или срок её действия истёк.")
            return

        member = await service.get_member(reminder.id, db_user.id)
        if member is not None and member.status.value == "active":
            await message.answer("Вы уже подключены к этому общему напоминанию.")
            return
        if member is not None and member.status.value == "removed":
            await message.answer("Владелец удалил вас из этого напоминания. Повторное подключение недоступно.")
            return

        member_count = await service.active_member_count(reminder.id)
        await state.update_data(
            pending_shared_join_id=reminder.id,
            pending_shared_join_hash=hash_invite_token(token),
        )
        await message.answer(
            shared_reminder_card_text(reminder, member_count, db_user.timezone),
            reply_markup=shared_join_keyboard(reminder.id),
        )
        return

    await state.clear()
    sent = await message.answer(main_menu_text(), reply_markup=main_menu_keyboard())
    await remember_ui_message(state, sent)


@router.callback_query(MainMenuCallback.filter(F.action == "back_main"))
async def back_to_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render_callback(callback, state, main_menu_text(), reply_markup=main_menu_keyboard())


@router.callback_query(MainMenuCallback.filter(F.action == "noop"))
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()
