from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated, validated_patch
from app.database import get_db
from app.models import Show
from app.shows.schemas import MAX_EPISODES, ResourceId, ShowPatch, ShowPayload, ShowView
from app.shows.service import owned_show, set_completion_date, user_today

router = APIRouter(prefix="/api/shows", tags=["shows"])


@router.get("", response_model=list[ShowView])
def list_shows(
    identity: Identity = Depends(authenticated), db: Session = Depends(get_db)
):
    return db.scalars(
        select(Show).where(Show.user_id == identity.user.id).order_by(Show.id.desc())
    ).all()


@router.post("", response_model=ShowView, status_code=201)
def create_show(
    payload: ShowPayload,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    values = payload.model_dump()
    set_completion_date(values, identity.user.timezone)
    show = Show(user_id=identity.user.id, **values)
    db.add(show)
    db.commit()
    return show


@router.get("/{item_id}", response_model=ShowView)
def get_show(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    return owned_show(db, item_id, identity.user.id)


@router.patch("/{item_id}", response_model=ShowView)
def update_show(
    item_id: ResourceId,
    payload: ShowPatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    show = owned_show(db, item_id, identity.user.id)
    values = validated_patch(ShowPayload, show, payload).model_dump()
    set_completion_date(values, identity.user.timezone, show.status)
    for key, value in values.items():
        setattr(show, key, value)
    db.commit()
    return show


@router.delete("/{item_id}", status_code=204)
def delete_show(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    db.delete(owned_show(db, item_id, identity.user.id))
    db.commit()


@router.post("/{item_id}/advance", response_model=ShowView)
def advance_show(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    show = owned_show(db, item_id, identity.user.id)
    if show.total is None or show.progress < show.total:
        if show.progress >= MAX_EPISODES:
            raise HTTPException(400, "集数已达到支持的上限（1,000,000）")
        show.progress += 1
        show.status = "completed" if show.progress == show.total else "watching"
        if show.status == "completed" and show.completed_on is None:
            show.completed_on = user_today(identity.user.timezone)
    db.commit()
    return show
