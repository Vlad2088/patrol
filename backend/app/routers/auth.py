"""Аутентификация: логин, refresh."""
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentUser, get_current_user
from app.core.security import create_access_token, decode_token, verify_password
from app.db import get_db
from app.models import User, UserRole
from app.schemas import LoginIn, RefreshIn, TokenPair

router = APIRouter()


@router.post("/auth/login", response_model=TokenPair)
def login(body: LoginIn, db=Depends(get_db)) -> TokenPair:
    user = db.scalar(select(User).where(User.login == body.login))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Пользователь отключён")

    from app.core.security import create_refresh_token

    return TokenPair(
        access=create_access_token(user.id, user.role),
        refresh=create_refresh_token(user.id, user.role),
        role=user.role,
        full_name=user.full_name,
    )


@router.post("/auth/refresh", response_model=dict)
def refresh(body: RefreshIn, db=Depends(get_db)) -> dict:
    try:
        payload = decode_token(body.refresh)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh недействителен")
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Неверный тип токена")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    return {
        "access": create_access_token(user.id, user.role),
        "refresh": create_refresh_token(user.id, user.role),
    }


@router.get("/auth/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"id": user.id, "login": user.login, "full_name": user.full_name, "role": user.role}
