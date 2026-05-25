from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import User


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def get_or_create_user(self, telegram_user: TelegramUser) -> User:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_user.id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                timezone=self.settings.default_timezone,
            )
            self.session.add(user)
        else:
            user.username = telegram_user.username
            user.first_name = telegram_user.first_name

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_timezone(self, user: User, timezone_name: str) -> User:
        user.timezone = timezone_name
        await self.session.commit()
        await self.session.refresh(user)
        return user

