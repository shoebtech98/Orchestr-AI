import re


def clean_text(text: str) -> str:
    """Collapse all whitespace runs to single spaces and trim the result."""
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 40) -> list[str]:
    """Split cleaned text into word-based chunks with a fixed overlap."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    words = clean_text(text).split()
    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap

    return chunks
