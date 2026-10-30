from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...auth_service import (
    AuthenticationDatabaseError,
    DuplicateEmailError,
    InvalidCredentialsError,
    authenticate_user,
    create_access_token,
    create_user,
)
from ...config import Settings
from ...models import User
from ..dependencies import get_db_session, get_settings

router = APIRouter(prefix="/auth", tags=["authentication"])


class RegistrationRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _database_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "database_unavailable", "message": "Authentication service unavailable."},
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegistrationRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> UserResponse:
    try:
        user = create_user(session, str(body.email), body.password)
    except DuplicateEmailError:
        raise HTTPException(
            status_code=409,
            detail={"code": "email_already_registered", "message": "An account with this email already exists."},
        ) from None
    except (AuthenticationDatabaseError, SQLAlchemyError) as exc:
        raise _database_unavailable() from exc
    return UserResponse(id=str(user.id), email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        user = authenticate_user(session, str(body.email), body.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "Invalid email or password."},
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except (AuthenticationDatabaseError, SQLAlchemyError) as exc:
        raise _database_unavailable() from exc
    return TokenResponse(
        access_token=create_access_token(user.id, settings),
        expires_in=settings.access_token_expire_minutes * 60,
    )
