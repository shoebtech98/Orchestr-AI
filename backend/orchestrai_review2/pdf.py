import hashlib
import uuid
from pathlib import Path

from pypdf import PdfReader

from .errors import EmptyPDFError, PDFProcessingError
from .text import clean_text


def extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    """Return non-empty, cleaned page text with 1-based page numbers."""
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {path}")

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            if reader.decrypt("") == 0:
                raise PDFProcessingError("The PDF is encrypted and requires a password.")

        pages = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = clean_text(page.extract_text() or "")
            if text:
                pages.append((page_number, text))
    except PDFProcessingError:
        raise
    except Exception as exc:
        raise PDFProcessingError(f"Could not extract text from PDF '{path}': {exc}") from exc

    if not pages:
        raise EmptyPDFError(f"No extractable text found in PDF: {path}")
    return pages


def document_id_for(path: Path) -> str:
    """Build a stable document ID from the PDF contents."""
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise PDFProcessingError(f"Could not read PDF '{path}': {exc}") from exc
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"orchestrai-review2:{digest}"))
