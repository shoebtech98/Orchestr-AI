from pathlib import Path

from .embeddings import EmbeddingModel
from .pdf import document_id_for, extract_pdf_pages
from .text import chunk_text
from .vector_store import QdrantStore


def index_pdf(
    pdf_path: Path,
    store: QdrantStore,
    embedder: EmbeddingModel,
    chunk_size: int = 200,
    overlap: int = 40,
    pages: list[tuple[int, str]] | None = None,
    filename: str | None = None,
    owner_id: str | None = None,
) -> dict:
    if pages is None:
        pages = extract_pdf_pages(pdf_path)
    document_id = document_id_for(pdf_path)
    records = []
    chunk_index = 0

    for page_number, page_text in pages:
        for text in chunk_text(page_text, chunk_size=chunk_size, overlap=overlap):
            records.append(
                {
                    "chunk_text": text,
                    "document_id": document_id,
                    "filename": filename or pdf_path.name,
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                }
            )
            if owner_id is not None:
                records[-1]["owner_id"] = owner_id
            chunk_index += 1

    if not records:
        raise ValueError(f"No text chunks could be created from PDF: {pdf_path}")

    vectors = embedder.encode([record["chunk_text"] for record in records])
    store.ensure_collection(embedder.dimension)
    store.upsert(document_id, records, vectors, owner_id=owner_id)
    return {
        "document_id": document_id,
        "filename": filename or pdf_path.name,
        "chunks_indexed": len(records),
    }


def search_documents(
    query: str,
    store: QdrantStore,
    embedder: EmbeddingModel,
    owner_id: str | None = None,
) -> list[dict]:
    if not query.strip():
        raise ValueError("Search query must not be empty.")
    vector = embedder.encode([query])[0]
    return store.search(vector, limit=5, owner_id=owner_id)
