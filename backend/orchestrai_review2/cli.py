import argparse
import json
import os
import sys
from pathlib import Path

from .embeddings import EmbeddingModel
from .errors import PipelineError
from .pipeline import index_pdf, search_documents
from .pdf import extract_pdf_pages
from .vector_store import QdrantStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orchestrai-review2",
        description="Index local research PDFs in Qdrant and search them semantically.",
    )
    parser.add_argument(
        "--qdrant-url",
        default=os.getenv("QDRANT_URL", "http://localhost:6333"),
        help="Qdrant URL (default: QDRANT_URL or http://localhost:6333)",
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("QDRANT_COLLECTION", "orchestrai_papers"),
        help="Qdrant collection name (default: QDRANT_COLLECTION or orchestrai_papers)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Index a local PDF.")
    index_parser.add_argument("pdf", type=Path, help="Path to a research PDF.")
    index_parser.add_argument("--chunk-size", type=int, default=200, help="Words per chunk.")
    index_parser.add_argument("--overlap", type=int, default=40, help="Overlapping words.")

    search_parser = subparsers.add_parser("search", help="Search indexed PDF chunks.")
    search_parser.add_argument("query", help="Semantic search query.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "index":
            pages = extract_pdf_pages(args.pdf)
            store = QdrantStore(url=args.qdrant_url, collection_name=args.collection)
            embedder = EmbeddingModel()
            result = index_pdf(
                args.pdf,
                store,
                embedder,
                chunk_size=args.chunk_size,
                overlap=args.overlap,
                pages=pages,
            )
        else:
            store = QdrantStore(url=args.qdrant_url, collection_name=args.collection)
            embedder = EmbeddingModel()
            result = {"results": search_documents(args.query, store, embedder)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (PipelineError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
