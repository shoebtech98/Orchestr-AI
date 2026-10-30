import os
from dataclasses import dataclass

from dotenv import load_dotenv
from sqlalchemy.exc import ArgumentError
from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class Settings:
    application_name: str = "OrchestrAI"
    api_prefix: str = "/api/v1"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "orchestrai_papers"
    max_upload_bytes: int = 20 * 1024 * 1024
    database_url: str = ""
    jwt_secret_key: str = ""
    access_token_expire_minutes: int = 30

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv()
        settings = cls(
            application_name=os.getenv("APP_NAME", cls.application_name),
            api_prefix=os.getenv("API_PREFIX", cls.api_prefix),
            qdrant_url=os.getenv("QDRANT_URL", cls.qdrant_url),
            qdrant_collection=os.getenv("QDRANT_COLLECTION", cls.qdrant_collection),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", cls.max_upload_bytes)),
            database_url=os.getenv("DATABASE_URL", ""),
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
            access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        )
        if not settings.application_name.strip():
            raise ValueError("APP_NAME must not be empty.")
        if not settings.api_prefix.startswith("/") or settings.api_prefix.endswith("/"):
            raise ValueError("API_PREFIX must start with '/' and must not end with '/'.")
        if not settings.qdrant_url.strip():
            raise ValueError("QDRANT_URL must not be empty.")
        if not settings.qdrant_collection.strip():
            raise ValueError("QDRANT_COLLECTION must not be empty.")
        if settings.max_upload_bytes <= 0:
            raise ValueError("MAX_UPLOAD_BYTES must be greater than zero.")
        if settings.access_token_expire_minutes <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero.")
        if settings.access_token_expire_minutes > 1440:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must not exceed 1440.")
        return settings

    def validate_database(self, require_postgresql: bool = True) -> None:
        if not self.database_url.strip():
            raise ValueError("DATABASE_URL must be configured before starting the API.")
        if require_postgresql:
            try:
                driver_name = make_url(self.database_url).drivername
            except (ArgumentError, ValueError) as exc:
                raise ValueError("DATABASE_URL is not a valid SQLAlchemy URL.") from exc
            if driver_name != "postgresql+psycopg":
                raise ValueError("DATABASE_URL must use PostgreSQL with the psycopg driver.")

    def validate_auth(self, require_postgresql: bool = True) -> None:
        self.validate_database(require_postgresql=require_postgresql)
        if not 1 <= self.access_token_expire_minutes <= 1440:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440.")
        key = self.jwt_secret_key.encode("utf-8")
        lower_key = self.jwt_secret_key.casefold()
        if (
            len(key) < 32
            or len(set(key)) < 8
            or any(marker in lower_key for marker in ("replace", "placeholder", "change-me"))
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be a non-placeholder key with at least 32 bytes "
                "and 8 distinct bytes."
            )
