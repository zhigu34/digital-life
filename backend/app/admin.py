from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Identity, administrator, revoke_sessions
from app.database import get_db
from app.models import User
from app.schemas import AdminUpdate, ResourceId, UserCreate, UserView
from app.security import hash_password

router = APIRouter(prefix="/api/admin/users", tags=["admin"])


@router.get("", response_model=list[UserView])
def list_users(identity: Identity = Depends(administrator), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("", response_model=UserView, status_code=201)
def create_user(
    payload: UserCreate, identity: Identity = Depends(administrator), db: Session = Depends(get_db)
):
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "用户名已存在") from None
    return user


@router.patch("/{user_id}", response_model=UserView)
def update_user(
    user_id: ResourceId,
    payload: AdminUpdate,
    identity: Identity = Depends(administrator),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    values = payload.model_dump(exclude_unset=True)
    if user.id == identity.user.id and values.get("is_active") is False:
        raise HTTPException(400, "不能停用当前管理员账号")
    password = values.pop("password", None)
    if password:
        user.password_hash = hash_password(password)
    for name, value in values.items():
        setattr(user, name, value)
    if password or values.get("is_active") is False:
        revoke_sessions(db, user.id)
    db.commit()
    return user
