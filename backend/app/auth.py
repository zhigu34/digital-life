import secrets
import time
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LoginSession, User
from app.schemas import Login, PasswordChange, Profile, ProfilePatch, UserView
from app.security import hash_password, token_hash, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@dataclass
class Identity:
    user: User
    session: LoginSession


def authenticated(request: Request, db: Session = Depends(get_db)) -> Identity:
    token = request.cookies.get(request.app.state.settings.cookie_name)
    session = db.get(LoginSession, token_hash(token)) if token else None
    if session is None or session.expires_at <= int(time.time()):
        raise HTTPException(401, "请先登录")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "请先登录")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(csrf.encode(), session.csrf_token.encode()):
            raise HTTPException(403, "CSRF 校验失败，请刷新后重试")
    return Identity(user, session)


def administrator(identity: Identity = Depends(authenticated)) -> Identity:
    if not identity.user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return identity


def revoke_sessions(db, user_id):
    db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))


def validated_patch(schema, record, patch):
    # Merge before validation so users can correct a value saved by an older
    # release even when current input validation has become stricter.
    current = {name: getattr(record, name) for name in schema.model_fields}
    try:
        return schema.model_validate({**current, **patch.model_dump(exclude_unset=True)})
    except ValidationError:
        raise HTTPException(422, "字段无效，请检查日期、范围及必填内容") from None


@router.post("/login")
def login(payload: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    valid = verify_password(payload.password, user.password_hash if user else None)
    if not valid or not user.is_active:
        raise HTTPException(401, "用户名或密码错误")
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= int(time.time())))
    old = request.cookies.get(request.app.state.settings.cookie_name)
    if old:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(old)))
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    settings = request.app.state.settings
    db.add(
        LoginSession(
            token_hash=token_hash(token),
            user_id=user.id,
            csrf_token=csrf,
            expires_at=int(time.time()) + settings.session_ttl,
        )
    )
    db.commit()
    response.set_cookie(
        settings.cookie_name,
        token,
        max_age=settings.session_ttl,
        httponly=True,
        secure=settings.secure_cookie,
        samesite="lax",
        path="/",
    )
    return {"user": UserView.model_validate(user), "csrf_token": csrf}


@router.get("/session")
def current_session(identity: Identity = Depends(authenticated)):
    return {
        "user": UserView.model_validate(identity.user),
        "csrf_token": identity.session.csrf_token,
    }


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    db.delete(identity.session)
    db.commit()
    response.delete_cookie(
        request.app.state.settings.cookie_name,
        path="/",
        secure=request.app.state.settings.secure_cookie,
        httponly=True,
        samesite="lax",
    )


@router.patch("/profile", response_model=UserView)
def update_profile(
    payload: ProfilePatch,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    values = validated_patch(Profile, identity.user, payload)
    for name, value in values.model_dump().items():
        setattr(identity.user, name, value)
    db.commit()
    return identity.user


@router.post("/password", status_code=204)
def change_password(
    payload: PasswordChange,
    request: Request,
    response: Response,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, identity.user.password_hash):
        raise HTTPException(400, "当前密码错误")
    identity.user.password_hash = hash_password(payload.new_password)
    revoke_sessions(db, identity.user.id)
    db.commit()
    response.delete_cookie(
        request.app.state.settings.cookie_name,
        path="/",
        secure=request.app.state.settings.secure_cookie,
        httponly=True,
        samesite="lax",
    )
