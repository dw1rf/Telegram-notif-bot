from __future__ import annotations

import asyncio
import logging

from app.bot import create_bot, create_dispatcher, set_main_commands
from app.config import get_settings
from app.database.session import SessionFactory, init_db
from app.services.healthcheck_service import HealthcheckService
from app.services.scheduler_service import SchedulerService


logger = logging.getLogger(__name__)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Using database: %s", settings.database_url)
    await init_db()

    bot = create_bot(settings)
    dispatcher = create_dispatcher()
    scheduler_service = SchedulerService(bot=bot, session_factory=SessionFactory)
    healthcheck_service = HealthcheckService(settings) if settings.uptime_enabled else None

    dispatcher["scheduler_service"] = scheduler_service

    async def on_startup() -> None:
        scheduler_service.start()
        await set_main_commands(bot)
        await scheduler_service.sync_reminders_on_startup()
        if healthcheck_service is not None:
            healthcheck_service.mark_ready()

    async def on_shutdown() -> None:
        if healthcheck_service is not None:
            healthcheck_service.mark_stopping()
        await scheduler_service.shutdown()
        await bot.session.close()
        if healthcheck_service is not None:
            await healthcheck_service.stop()

    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    if healthcheck_service is not None:
        await healthcheck_service.start()

    await dispatcher.start_polling(bot, scheduler_service=scheduler_service)


if __name__ == "__main__":
    asyncio.run(main())
