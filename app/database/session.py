from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database.base import Base


settings = get_settings()


SQLITE_ENUM_NORMALIZATION_STATEMENTS = (
    """
    UPDATE reminders
    SET repeat_type = lower(repeat_type)
    WHERE repeat_type IN ('NONE', 'DAILY', 'WEEKLY', 'MONTHLY')
    """,
    """
    UPDATE shared_reminders
    SET repeat_rule = lower(repeat_rule)
    WHERE repeat_rule IN ('NONE', 'DAILY', 'WEEKLY', 'MONTHLY')
    """,
    """
    UPDATE shared_reminders
    SET status = lower(status)
    WHERE status IN ('ACTIVE', 'CANCELLED', 'COMPLETED')
    """,
    """
    UPDATE shared_reminder_members
    SET role = lower(role)
    WHERE role IN ('OWNER', 'MEMBER')
    """,
    """
    UPDATE shared_reminder_members
    SET status = lower(status)
    WHERE status IN ('ACTIVE', 'MUTED', 'LEFT', 'REMOVED')
    """,
    """
    UPDATE reminder_delivery_log
    SET status = lower(status)
    WHERE status IN ('SENT', 'FAILED')
    """,
)


def ensure_database_directory(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return

    database_path = url.database
    if not database_path or database_path == ":memory:":
        return

    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


def is_sqlite_database(database_url: str) -> bool:
    return make_url(database_url).get_backend_name() == "sqlite"


engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    ensure_database_directory(settings.database_url)

    import app.database.models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        if is_sqlite_database(settings.database_url):
            for statement in SQLITE_ENUM_NORMALIZATION_STATEMENTS:
                await connection.execute(text(statement))
