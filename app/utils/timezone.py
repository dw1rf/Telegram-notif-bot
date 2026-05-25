from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.database.models import RepeatType


def get_timezone(timezone_name: str) -> ZoneInfo:
    return ZoneInfo(timezone_name)


def is_valid_timezone(timezone_name: str) -> bool:
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return False
    return True


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_utc(local_datetime: datetime, timezone_name: str) -> datetime:
    timezone = get_timezone(timezone_name)
    if local_datetime.tzinfo is None:
        local_datetime = local_datetime.replace(tzinfo=timezone)
    return local_datetime.astimezone(UTC)


def to_user_timezone(value: datetime, timezone_name: str) -> datetime:
    timezone = get_timezone(timezone_name)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(timezone)


def format_user_datetime(value: datetime, timezone_name: str) -> str:
    return to_user_timezone(value, timezone_name).strftime("%d.%m.%Y %H:%M")


def start_of_today(timezone_name: str) -> datetime:
    now_local = utc_now().astimezone(get_timezone(timezone_name))
    return now_local.replace(hour=0, minute=0, second=0, microsecond=0)


def _add_one_month(local_value: datetime) -> datetime:
    year = local_value.year
    month = local_value.month + 1
    if month > 12:
        month = 1
        year += 1
    day = min(local_value.day, calendar.monthrange(year, month)[1])
    return local_value.replace(year=year, month=month, day=day)


def calculate_next_occurrence(
    remind_at: datetime,
    repeat_type: RepeatType,
    timezone_name: str,
    reference_time: datetime | None = None,
) -> datetime:
    if repeat_type == RepeatType.NONE:
        return remind_at

    now_utc = reference_time or utc_now()
    local_value = to_user_timezone(remind_at, timezone_name)
    local_now = to_user_timezone(now_utc, timezone_name)

    while local_value <= local_now:
        if repeat_type == RepeatType.DAILY:
            local_value += timedelta(days=1)
        elif repeat_type == RepeatType.WEEKLY:
            local_value += timedelta(weeks=1)
        elif repeat_type == RepeatType.MONTHLY:
            local_value = _add_one_month(local_value)
        else:
            break

    return local_value.astimezone(UTC)

