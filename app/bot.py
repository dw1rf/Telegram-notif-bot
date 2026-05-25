from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import Settings
from app.database.session import SessionFactory
from app.handlers.reminders import router as reminders_router
from app.handlers.settings import router as settings_router
from app.handlers.shared_reminders import router as shared_reminders_router
from app.handlers.start import router as start_router
from app.middlewares.db import DbSessionMiddleware


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher["session_factory"] = SessionFactory
    dispatcher.update.middleware(DbSessionMiddleware(SessionFactory))
    dispatcher.include_router(start_router)
    dispatcher.include_router(reminders_router)
    dispatcher.include_router(shared_reminders_router)
    dispatcher.include_router(settings_router)
    return dispatcher


async def set_main_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть главное меню"),
            BotCommand(command="new_shared_reminder", description="Создать общее напоминание"),
            BotCommand(command="my_shared_reminders", description="Мои общие напоминания"),
        ]
    )
