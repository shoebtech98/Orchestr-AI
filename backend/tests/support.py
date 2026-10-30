from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from orchestrai_review2.auth_service import create_access_token, create_user
from orchestrai_review2.api import create_app
from orchestrai_review2.config import Settings
from orchestrai_review2.models import Base

TEST_SECRET = "test-only-signing-key-with-enough-distinct-characters"


class FakeRetrievalService:
    def __init__(self):
        self.indexed_path: Path | None = None
        self.indexed_bytes: bytes | None = None
        self.indexed_filename: str | None = None
        self.indexed_owner_id: str | None = None
        self.query: str | None = None
        self.search_owner_id: str | None = None
        self.index_error: Exception | None = None
        self.search_error: Exception | None = None
        self.health_error: Exception | None = None

    def check_qdrant(self) -> None:
        if self.health_error:
            raise self.health_error

    def index_pdf(self, pdf_path: Path, filename: str, owner_id: str | None = None) -> dict:
        self.indexed_path = pdf_path
        self.indexed_bytes = pdf_path.read_bytes()
        self.indexed_filename = filename
        self.indexed_owner_id = owner_id
        if self.index_error:
            raise self.index_error
        return {
            "document_id": "doc-123",
            "filename": filename,
            "chunks_indexed": 2,
        }

    def search(self, query: str, owner_id: str | None = None) -> list[dict]:
        self.query = query
        self.search_owner_id = owner_id
        if self.search_error:
            raise self.search_error
        return [
            {
                "score": 0.9,
                "document_id": "doc-123",
                "filename": "paper.pdf",
                "page_number": 2,
                "chunk_index": 1,
                "chunk_text": "Relevant paper content.",
            }
        ]

    def close(self) -> None:
        pass


@contextmanager
def client_context(
    service: FakeRetrievalService | None = None,
    settings_overrides: dict | None = None,
) -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    settings_values = {
        "database_url": "sqlite://",
        "jwt_secret_key": TEST_SECRET,
    }
    settings_values.update(settings_overrides or {})
    settings = Settings(**settings_values)
    retrieval_service = service or FakeRetrievalService()
    app = create_app(
        settings=settings,
        service=retrieval_service,
        session_factory=session_factory,
    )
    try:
        with TestClient(app) as client:
            with session_factory() as session:
                user = create_user(session, "test@example.com", "correct-horse-battery")
            client.auth_headers = {
                "Authorization": f"Bearer {create_access_token(user.id, settings)}"
            }
            client.session_factory = session_factory
            client.settings = settings
            yield client
    finally:
        engine.dispose()
