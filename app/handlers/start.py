from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.database.models import User
from app.keyboards.callbacks import MainMenuCallback
from app.keyboards.main import main_menu_keyboard


router = Router()


@router.message(CommandStart())
async def command_start(message: Message, db_user: User) -> None:
    await message.answer(
        "🔔 Напоминалка",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(MainMenuCallback.filter(F.action == "back_main"))
async def back_to_main(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🔔 Напоминалка",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(MainMenuCallback.filter(F.action == "noop"))
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()

