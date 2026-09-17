"""Business rules shared by the dedicated Shows endpoints."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Show


def owned_show(db: Session, item_id: int, user_id: int) -> Show:
    show = db.scalar(select(Show).where(Show.id == item_id, Show.user_id == user_id))
    if show is None:
        raise HTTPException(404, "记录不存在")
    return show


def user_today(timezone: str, now: datetime | None = None) -> date:
    instant = now or datetime.now(UTC)
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = UTC
    return instant.astimezone(zone).date()


def set_completion_date(
    values: dict, timezone: str, previous_status: str | None = None
) -> None:
    if (
        values["status"] == "completed"
        and previous_status != "completed"
        and values["completed_on"] is None
    ):
        values["completed_on"] = user_today(timezone)
