from pathlib import Path

from .config import Settings
from .embeddings import EmbeddingModel
from .pipeline import index_pdf, search_documents
from .vector_store import QdrantStore


class RetrievalService:
    def __init__(self, settings: Settings):
        self.store = QdrantStore(
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
        )
        self._embedder: EmbeddingModel | None = None

    @property
    def embedder(self) -> EmbeddingModel:
        if self._embedder is None:
            self._embedder = EmbeddingModel()
        return self._embedder

    def check_qdrant(self) -> None:
        self.store.check_connection()

    def index_pdf(self, pdf_path: Path, filename: str, owner_id: str | None = None) -> dict:
        return index_pdf(
            pdf_path,
            self.store,
            self.embedder,
            filename=filename,
            owner_id=owner_id,
        )

    def search(self, query: str, owner_id: str | None = None) -> list[dict]:
        return search_documents(query, self.store, self.embedder, owner_id=owner_id)

    def close(self) -> None:
        self.store.close()
