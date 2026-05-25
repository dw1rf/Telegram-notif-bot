from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Reminder, RepeatType, User


class ReminderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_reminder(
        self,
        user_id: int,
        text: str,
        remind_at: datetime,
        repeat_type: RepeatType,
    ) -> Reminder:
        reminder = Reminder(
            user_id=user_id,
            text=text,
            remind_at=remind_at.astimezone(UTC),
            repeat_type=repeat_type,
            is_active=True,
        )
        self.session.add(reminder)
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def get_user_reminders(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 5,
        recurring_only: bool = False,
    ) -> tuple[list[Reminder], int, int]:
        filters = [Reminder.user_id == user_id, Reminder.is_active.is_(True)]
        if recurring_only:
            filters.append(Reminder.repeat_type != RepeatType.NONE)

        total = await self.session.scalar(select(func.count(Reminder.id)).where(*filters)) or 0
        total_pages = max((total + page_size - 1) // page_size, 1)
        page = min(max(page, 1), total_pages)

        result = await self.session.execute(
            select(Reminder)
            .where(*filters)
            .order_by(Reminder.remind_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total_pages, total

    async def get_user_reminder(self, reminder_id: int, user_id: int) -> Reminder | None:
        result = await self.session.execute(
            select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_reminder_for_scheduler(self, reminder_id: int) -> Reminder | None:
        result = await self.session.execute(
            select(Reminder)
            .options(selectinload(Reminder.user))
            .where(Reminder.id == reminder_id)
        )
        return result.scalar_one_or_none()

    async def get_all_active_reminders(self) -> list[Reminder]:
        result = await self.session.execute(
            select(Reminder)
            .options(selectinload(Reminder.user))
            .where(Reminder.is_active.is_(True))
            .order_by(Reminder.remind_at.asc())
        )
        return list(result.scalars().all())

    async def update_text(self, reminder: Reminder, text: str) -> Reminder:
        reminder.text = text
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def update_time(self, reminder: Reminder, remind_at: datetime) -> Reminder:
        reminder.remind_at = remind_at.astimezone(UTC)
        reminder.is_active = True
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def update_repeat_type(self, reminder: Reminder, repeat_type: RepeatType) -> Reminder:
        reminder.repeat_type = repeat_type
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def mark_inactive(self, reminder: Reminder) -> Reminder:
        reminder.is_active = False
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def activate_with_new_time(self, reminder: Reminder, remind_at: datetime) -> Reminder:
        reminder.remind_at = remind_at.astimezone(UTC)
        reminder.is_active = True
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def delete_reminder(self, reminder: Reminder) -> None:
        await self.session.delete(reminder)
        await self.session.commit()

    async def create_test_reminder(self, user_id: int) -> Reminder:
        remind_at = datetime.now(UTC) + timedelta(minutes=1)
        return await self.create_reminder(
            user_id=user_id,
            text="Тестовое напоминание. Если вы это видите, доставка работает.",
            remind_at=remind_at,
            repeat_type=RepeatType.NONE,
        )

