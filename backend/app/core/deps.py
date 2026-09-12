"""FastAPI-зависимости: текущий пользователь, RBAC."""
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token
from app.db import get_db
from app.models import User, UserRole

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: int
    login: str
    full_name: str
    role: UserRole


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db=Depends(get_db),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Токен недействителен или истёк",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Неверный тип токена")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или отключён",
        )
    return CurrentUser(
        id=user.id, login=user.login, full_name=user.full_name, role=user.role
    )


def require_dispatcher(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != UserRole.DISPATCHER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Требуется роль диспетчера")
    return user


def require_guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != UserRole.GUARD:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Требуется роль охранника")
    return user
