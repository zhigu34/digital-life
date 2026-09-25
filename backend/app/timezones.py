"""Portable timezone helpers shared by the API modules.

This lives outside the feature packages so modules that may not import each
other (records / maintenance / shows / ledger) can still agree on what "today"
means for a given profile, and so the portable-zone rule has a single source.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SYSTEM_ONLY_NAMES = frozenset({"Factory", "localtime", "posixrules"})
SYSTEM_ONLY_PREFIXES = ("posix/", "right/")


def validate_timezone(value: str) -> str:
    """Reject system-only zone names and require a portable IANA timezone."""

    if value in SYSTEM_ONLY_NAMES or value.startswith(SYSTEM_ONLY_PREFIXES):
        raise ValueError("Timezone must be a portable IANA timezone")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Timezone must be a valid IANA timezone") from None
    return value


def user_today(timezone: str, now: datetime | None = None) -> date:
    """The calendar date in the user's zone, falling back to UTC.

    Stored profiles can name a zone this runtime cannot load; the fallback keeps
    login, export and repair paths from failing on old data.
    """

    instant = now or datetime.now(UTC)
    try:
        zone = ZoneInfo(validate_timezone(timezone))
    except (ZoneInfoNotFoundError, ValueError):
        zone = UTC
    return instant.astimezone(zone).date()
