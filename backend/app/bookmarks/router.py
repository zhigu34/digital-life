from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated, validated_patch
from app.bookmarks.schemas import (
    BookmarkPatch,
    BookmarkPayload,
    BookmarkView,
    TitleResult,
    UrlRequest,
)
from app.bookmarks.service import fetch_title, now, owned_bookmark
from app.database import get_db
from app.models import Bookmark
from app.schemas import ResourceId

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


@router.get("", response_model=list[BookmarkView])
def list_bookmarks(
    q: str | None = Query(default=None, max_length=120),
    folder: str | None = Query(default=None, max_length=60),
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    statement = select(Bookmark).where(Bookmark.user_id == identity.user.id)
    keyword = (q or "").strip()
    if keyword:
        pattern = f"%{keyword}%"
        statement = statement.where(
            or_(
                Bookmark.title.like(pattern),
                Bookmark.url.like(pattern),
                Bookmark.note.like(pattern),
            )
        )
    # An empty string means "ungrouped"; None means "every group".
    if folder is not None:
        statement = statement.where(
            Bookmark.folder.is_(None) if folder == "" else Bookmark.folder == folder
        )
    return db.scalars(statement.order_by(Bookmark.starred.desc(), Bookmark.id.desc())).all()


@router.post("", response_model=BookmarkView, status_code=201)
def create_bookmark(
    payload: BookmarkPayload,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    bookmark = Bookmark(user_id=identity.user.id, created_at=now(), **payload.model_dump())
    db.add(bookmark)
    db.commit()
    return bookmark


@router.post("/title", response_model=TitleResult)
def lookup_title(
    payload: UrlRequest,
    request: Request,
    identity: Identity = Depends(authenticated),
):
    if request.app.state.settings.metadata_disabled:
        raise HTTPException(503, "元数据获取未启用（DIGITAL_LIFE_DISABLE_METADATA）")
    return {"title": fetch_title(payload.url)}


@router.get("/{item_id}", response_model=BookmarkView)
def get_bookmark(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    return owned_bookmark(db, item_id, identity.user.id)


@router.patch("/{item_id}", response_model=BookmarkView)
def update_bookmark(
    item_id: ResourceId,
    payload: BookmarkPatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    bookmark = owned_bookmark(db, item_id, identity.user.id)
    values = validated_patch(BookmarkPayload, bookmark, payload).model_dump()
    for key, value in values.items():
        setattr(bookmark, key, value)
    db.commit()
    return bookmark


@router.delete("/{item_id}", status_code=204)
def delete_bookmark(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    db.delete(owned_bookmark(db, item_id, identity.user.id))
    db.commit()


@router.post("/{item_id}/visit", response_model=BookmarkView)
def visit_bookmark(
    item_id: ResourceId,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    bookmark = owned_bookmark(db, item_id, identity.user.id)
    bookmark.visit_count += 1
    bookmark.last_visited_at = now()
    db.commit()
    return bookmark
