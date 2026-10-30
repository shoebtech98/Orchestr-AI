import uuid
from collections.abc import Iterator

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth_service import decode_access_token
from ..config import Settings
from ..models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db_session(request: Request) -> Iterator[Session]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail={"code": "database_unavailable"})
    with session_factory() as session:
        yield session


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail={"code": "invalid_authentication", "message": "Valid bearer credentials required."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        user_id: uuid.UUID = decode_access_token(credentials.credentials, settings)
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise unauthorized from None
    try:
        user = session.get(User, user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "database_unavailable", "message": "Authentication service unavailable."},
        ) from exc
    if user is None:
        raise unauthorized
    return user
