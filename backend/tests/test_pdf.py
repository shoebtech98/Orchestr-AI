import pytest
from pypdf import PdfWriter

from orchestrai_review2.errors import EmptyPDFError
from orchestrai_review2.pdf import extract_pdf_pages


def test_extract_pdf_pages_rejects_empty_pdf(tmp_path):
    pdf_path = tmp_path / "empty.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as pdf_file:
        writer.write(pdf_file)

    with pytest.raises(EmptyPDFError):
        extract_pdf_pages(pdf_path)


def test_extract_pdf_pages_reports_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="PDF file not found"):
        extract_pdf_pages(tmp_path / "missing.pdf")
