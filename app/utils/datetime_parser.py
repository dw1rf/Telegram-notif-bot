from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.utils.timezone import get_timezone, to_utc, utc_now


DATETIME_PATTERN = re.compile(r"^(?P<date>\d{2}\.\d{2}\.\d{4})\s+(?P<time>\d{2}:\d{2})$")
IN_MINUTES_PATTERN = re.compile(r"^через\s+(?P<value>\d+)\s+мин(?:ут|уты|уту)?$", re.IGNORECASE)
IN_HOURS_PATTERN = re.compile(r"^через\s+(?P<value>\d+)\s+час(?:ов|а)?$", re.IGNORECASE)
TODAY_PATTERN = re.compile(r"^сегодня\s+(?P<time>\d{2}:\d{2})$", re.IGNORECASE)
TOMORROW_PATTERN = re.compile(r"^завтра\s+(?P<time>\d{2}:\d{2})$", re.IGNORECASE)


class DateParseError(ValueError):
    pass


def parse_user_datetime(raw_value: str, timezone_name: str) -> datetime:
    value = raw_value.strip().lower()
    timezone = get_timezone(timezone_name)
    local_now = utc_now().astimezone(timezone)

    if match := IN_MINUTES_PATTERN.match(value):
        minutes = int(match.group("value"))
        return (utc_now() + timedelta(minutes=minutes)).replace(second=0, microsecond=0)

    if match := IN_HOURS_PATTERN.match(value):
        hours = int(match.group("value"))
        return (utc_now() + timedelta(hours=hours)).replace(second=0, microsecond=0)

    if match := TODAY_PATTERN.match(value):
        parsed_time = datetime.strptime(match.group("time"), "%H:%M").time()
        local_datetime = local_now.replace(
            hour=parsed_time.hour,
            minute=parsed_time.minute,
            second=0,
            microsecond=0,
        )
        if local_datetime <= local_now:
            raise DateParseError("Время на сегодня уже прошло.")
        return to_utc(local_datetime, timezone_name)

    if match := TOMORROW_PATTERN.match(value):
        parsed_time = datetime.strptime(match.group("time"), "%H:%M").time()
        local_datetime = (local_now + timedelta(days=1)).replace(
            hour=parsed_time.hour,
            minute=parsed_time.minute,
            second=0,
            microsecond=0,
        )
        return to_utc(local_datetime, timezone_name)

    if match := DATETIME_PATTERN.match(value):
        local_datetime = datetime.strptime(
            f"{match.group('date')} {match.group('time')}",
            "%d.%m.%Y %H:%M",
        ).replace(tzinfo=timezone)
        if local_datetime <= local_now:
            raise DateParseError("Указанное время уже прошло.")
        return to_utc(local_datetime, timezone_name)

    raise DateParseError(
        "Не удалось распознать дату. Используйте формат DD.MM.YYYY HH:MM или фразы вроде 'завтра 18:00'."
    )
