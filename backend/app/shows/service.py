"""Business rules shared by the dedicated Shows endpoints."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Show
from app.timezones import user_today


def owned_show(db: Session, item_id: int, user_id: int) -> Show:
    show = db.scalar(select(Show).where(Show.id == item_id, Show.user_id == user_id))
    if show is None:
        raise HTTPException(404, "记录不存在")
    return show


def set_completion_date(values: dict, timezone: str, previous_status: str | None = None) -> None:
    if (
        values["status"] == "completed"
        and previous_status != "completed"
        and values["completed_on"] is None
    ):
        values["completed_on"] = user_today(timezone)
