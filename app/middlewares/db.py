from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TelegramUser
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.services.user_service import UserService


logger = logging.getLogger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            telegram_user = data.get("event_from_user")
            if isinstance(telegram_user, TelegramUser):
                data["db_user"] = await UserService(session).get_or_create_user(telegram_user)

            try:
                return await handler(event, data)
            except Exception:
                logger.exception("Unhandled error while processing update")
                raise

