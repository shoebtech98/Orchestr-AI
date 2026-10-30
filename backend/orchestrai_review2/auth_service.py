import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .config import Settings
from .models import User

password_hasher = PasswordHasher()
_DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-account-password")
_JWT_ISSUER = "orchestrai"
_JWT_AUDIENCE = "orchestrai-api"


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AuthenticationDatabaseError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(session: Session, email: str, password: str) -> User:
    normalized_email = normalize_email(email)
    user = User(email=normalized_email, password_hash=password_hasher.hash(password))
    try:
        with session.begin():
            session.add(user)
            session.flush()
    except IntegrityError as exc:
        if _is_duplicate_email_error(exc):
            raise DuplicateEmailError from exc
        raise AuthenticationDatabaseError from exc
    return user


def authenticate_user(session: Session, email: str, password: str) -> User:
    try:
        user = session.scalar(select(User).where(User.email == normalize_email(email)))
    except SQLAlchemyError as exc:
        raise AuthenticationDatabaseError from exc

    stored_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    try:
        password_hasher.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        raise InvalidCredentialsError from None
    if user is None:
        raise InvalidCredentialsError
    return user


def create_access_token(user_id: uuid.UUID | str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    claims = {
        "sub": str(user_id),
        "iat": now,
        "exp": expires_at,
        "iss": _JWT_ISSUER,
        "aud": _JWT_AUDIENCE,
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    claims = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=["HS256"],
        issuer=_JWT_ISSUER,
        audience=_JWT_AUDIENCE,
        options={"require": ["sub", "exp", "iat", "iss", "aud"]},
    )
    try:
        return uuid.UUID(claims["sub"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise jwt.InvalidTokenError("Invalid subject claim.") from exc


def _is_duplicate_email_error(error: IntegrityError) -> bool:
    original = error.orig
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint_name == "uq_users_email":
        return True
    message = str(original).lower()
    return "users.email" in message and (
        "unique" in message or "duplicate" in message
    )
