from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database.models import RepeatType
from app.keyboards.reminders import fired_reminder_keyboard
from app.services.reminder_service import ReminderService
from app.utils.timezone import calculate_next_occurrence, utc_now


logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, bot: Bot, session_factory: async_sessionmaker) -> None:
        self.bot = bot
        self.session_factory = session_factory
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def _job_id(self, reminder_id: int) -> str:
        return f"reminder:{reminder_id}"

    def schedule_reminder(self, reminder_id: int, remind_at) -> None:
        self.scheduler.add_job(
            self.send_due_reminder,
            trigger=DateTrigger(run_date=remind_at),
            id=self._job_id(reminder_id),
            replace_existing=True,
            kwargs={"reminder_id": reminder_id},
            misfire_grace_time=300,
        )

    def remove_job(self, reminder_id: int) -> None:
        job_id = self._job_id(reminder_id)
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    async def sync_reminders_on_startup(self) -> None:
        async with self.session_factory() as session:
            service = ReminderService(session)
            reminders = await service.get_all_active_reminders()

            for reminder in reminders:
                try:
                    if reminder.remind_at <= utc_now():
                        if reminder.repeat_type == RepeatType.NONE:
                            await self.send_due_reminder(reminder.id)
                        else:
                            next_run = calculate_next_occurrence(
                                reminder.remind_at,
                                reminder.repeat_type,
                                reminder.user.timezone,
                            )
                            await service.activate_with_new_time(reminder, next_run)
                            self.schedule_reminder(reminder.id, next_run)
                    else:
                        self.schedule_reminder(reminder.id, reminder.remind_at)
                except Exception:
                    logger.exception("Failed to sync reminder %s", reminder.id)

    async def send_due_reminder(self, reminder_id: int) -> None:
        async with self.session_factory() as session:
            service = ReminderService(session)
            reminder = await service.get_reminder_for_scheduler(reminder_id)
            if reminder is None or reminder.user is None:
                return

            if reminder.repeat_type == RepeatType.NONE and not reminder.is_active:
                return

            try:
                await self.bot.send_message(
                    chat_id=reminder.user.telegram_id,
                    text=f"🔔 Напоминание\n\n{reminder.text}",
                    reply_markup=fired_reminder_keyboard(reminder.id),
                )
            except Exception:
                logger.exception("Failed to send reminder %s", reminder.id)
                return

            if reminder.repeat_type == RepeatType.NONE:
                await service.mark_inactive(reminder)
                self.remove_job(reminder.id)
                return

            next_run = calculate_next_occurrence(
                reminder.remind_at,
                reminder.repeat_type,
                reminder.user.timezone,
            )
            await service.activate_with_new_time(reminder, next_run)
            self.schedule_reminder(reminder.id, next_run)

    async def snooze_reminder(self, reminder_id: int, delta: timedelta) -> bool:
        async with self.session_factory() as session:
            service = ReminderService(session)
            reminder = await service.get_reminder_for_scheduler(reminder_id)
            if reminder is None:
                return False

            new_time = utc_now() + delta
            await service.activate_with_new_time(reminder, new_time)
            self.schedule_reminder(reminder.id, new_time)
            return True

