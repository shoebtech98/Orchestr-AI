from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from orchestrai_review2.auth_service import create_access_token, decode_access_token
from orchestrai_review2.api import create_app
from orchestrai_review2.config import Settings
from orchestrai_review2.models import User
from support import TEST_SECRET, FakeRetrievalService, client_context


def test_registration_normalizes_email_and_login_returns_access_token():
    with client_context() as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": "  New.User@Example.COM ", "password": "correct-horse-battery"},
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "NEW.USER@example.com", "password": "correct-horse-battery"},
        )

        assert registered.status_code == 201
        assert registered.json()["email"] == "new.user@example.com"
        assert UUID(registered.json()["id"])
        assert login.status_code == 200
        assert login.json()["token_type"] == "bearer"
        assert login.json()["expires_in"] == 1800
        assert decode_access_token(login.json()["access_token"], client.settings) == UUID(
            registered.json()["id"]
        )


def test_password_is_stored_as_argon2_hash():
    with client_context() as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "hashed@example.com", "password": "correct-horse-battery"},
        )
        with client.session_factory() as session:
            user = session.scalar(select(User).where(User.email == "hashed@example.com"))

    assert response.status_code == 201
    assert user is not None
    assert user.password_hash != "correct-horse-battery"
    assert user.password_hash.startswith("$argon2")
    assert PasswordHasher().verify(user.password_hash, "correct-horse-battery")


def test_duplicate_registration_returns_conflict():
    with client_context() as client:
        first = client.post(
            "/api/v1/auth/register",
            json={"email": "duplicate@example.com", "password": "correct-horse-battery"},
        )
        duplicate = client.post(
            "/api/v1/auth/register",
            json={"email": "DUPLICATE@example.com", "password": "another-correct-password"},
        )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "email_already_registered"


def test_login_uses_same_error_for_unknown_email_and_wrong_password():
    with client_context() as client:
        unknown = client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": "incorrect-password"},
        )
        wrong_password = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "incorrect-password"},
        )

    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json()


def test_password_registration_validation():
    with client_context() as client:
        short_password = client.post(
            "/api/v1/auth/register",
            json={"email": "short@example.com", "password": "short"},
        )
        malformed_email = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "correct-horse-battery"},
        )

    assert short_password.status_code == 422
    assert malformed_email.status_code == 422


def test_jwt_decoder_accepts_valid_token_and_rejects_malformed_expired_and_bad_signature():
    settings = Settings(database_url="sqlite://", jwt_secret_key=TEST_SECRET)
    user_id = UUID("b1bc7d77-b407-468e-96db-44ded7306197")
    valid_token = create_access_token(user_id, settings)
    assert decode_access_token(valid_token, settings) == user_id

    expired_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    expired_token = jwt.encode(
        {
            "sub": str(user_id),
            "iat": expired_at - timedelta(minutes=1),
            "exp": expired_at,
            "iss": "orchestrai",
            "aud": "orchestrai-api",
        },
        TEST_SECRET,
        algorithm="HS256",
    )
    invalid_signature = jwt.encode(
        {
            "sub": str(user_id),
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iss": "orchestrai",
            "aud": "orchestrai-api",
        },
        "different-secret-with-at-least-32-bytes",
        algorithm="HS256",
    )

    for token in ("not-a-jwt", expired_token, invalid_signature):
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(token, settings)


@pytest.mark.parametrize(
    ("database_url", "jwt_secret"),
    [
        ("", TEST_SECRET),
        ("sqlite://", TEST_SECRET),
        ("postgresql://user:password@localhost/orchestrai", TEST_SECRET),
        ("postgresql+psycopg://user:password@localhost/orchestrai", "short"),
        (
            "postgresql+psycopg://user:password@localhost/orchestrai",
            "REPLACE_WITH_A_RANDOM_SIGNING_KEY_123456789",
        ),
    ],
)
def test_auth_configuration_rejects_missing_or_insecure_values(database_url, jwt_secret):
    settings = Settings(database_url=database_url, jwt_secret_key=jwt_secret)

    with pytest.raises(ValueError):
        settings.validate_auth()


def test_application_startup_fails_when_database_or_jwt_settings_are_missing():
    app = create_app(settings=Settings(), service=FakeRetrievalService())

    with pytest.raises(ValueError, match="DATABASE_URL"):
        with TestClient(app):
            pass


@pytest.mark.parametrize("authorization", [None, "Bearer malformed-token"])
def test_protected_endpoints_reject_missing_or_invalid_tokens(authorization):
    service = FakeRetrievalService()
    with client_context(service) as client:
        headers = {} if authorization is None else {"Authorization": authorization}
        response = client.post(
            "/api/v1/search",
            json={"query": "private content"},
            headers=headers,
        )

    assert response.status_code == 401
    assert service.query is None


def test_valid_token_can_access_protected_endpoint():
    service = FakeRetrievalService()
    with client_context(service) as client:
        response = client.post(
            "/api/v1/search",
            json={"query": "private content"},
            headers=client.auth_headers,
        )

    assert response.status_code == 200
    assert service.search_owner_id is not None


def test_registration_database_failure_returns_503_and_rolls_back():
    with client_context() as client:
        def fail_before_flush(session, flush_context, instances):
            raise OperationalError("INSERT", {}, RuntimeError("simulated database failure"))

        event.listen(Session, "before_flush", fail_before_flush)
        try:
            response = client.post(
                "/api/v1/auth/register",
                json={"email": "rollback@example.com", "password": "correct-horse-battery"},
            )
        finally:
            event.remove(Session, "before_flush", fail_before_flush)

        with client.session_factory() as session:
            user = session.scalar(select(User).where(User.email == "rollback@example.com"))

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"
    assert user is None
