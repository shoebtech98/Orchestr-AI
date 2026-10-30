from orchestrai_review2.errors import EmptyPDFError, VectorStoreError
from support import FakeRetrievalService, client_context


def test_health_endpoint_reports_application_and_qdrant_status():
    service = FakeRetrievalService()
    with client_context(service) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "application": {"name": "OrchestrAI", "status": "healthy"},
        "dependencies": {"qdrant": {"status": "healthy"}},
    }


def test_health_endpoint_is_degraded_when_qdrant_is_unavailable():
    service = FakeRetrievalService()
    service.health_error = VectorStoreError("connection refused")
    with client_context(service) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "application": {"name": "OrchestrAI", "status": "healthy"},
        "dependencies": {"qdrant": {"status": "unavailable"}},
    }


def test_index_endpoint_returns_metadata_and_associates_authenticated_owner():
    service = FakeRetrievalService()
    with client_context(service) as client:
        response = client.post(
            "/api/v1/documents",
            files={"file": ("paper.pdf", b"%PDF-1.7 test content", "application/pdf")},
            headers=client.auth_headers,
        )

    assert response.status_code == 201
    assert response.json() == {
        "document_id": "doc-123",
        "filename": "paper.pdf",
        "chunks_indexed": 2,
    }
    assert service.indexed_filename == "paper.pdf"
    assert service.indexed_bytes == b"%PDF-1.7 test content"
    assert service.indexed_path is not None
    assert not service.indexed_path.exists()
    assert service.indexed_owner_id is not None


def test_index_endpoint_rejects_missing_or_unsupported_files():
    service = FakeRetrievalService()
    with client_context(service) as client:
        missing_file = client.post("/api/v1/documents", headers=client.auth_headers)
        unsupported_file = client.post(
            "/api/v1/documents",
            files={"file": ("notes.txt", b"not a PDF", "text/plain")},
            headers=client.auth_headers,
        )

    assert missing_file.status_code == 422
    assert unsupported_file.status_code == 415
    assert unsupported_file.json()["detail"]["code"] == "unsupported_file_type"


def test_index_endpoint_rejects_oversized_and_unreadable_pdfs():
    service = FakeRetrievalService()
    with client_context(service, settings_overrides={"max_upload_bytes": 4}) as client:
        oversized = client.post(
            "/api/v1/documents",
            files={"file": ("paper.pdf", b"12345", "application/pdf")},
            headers=client.auth_headers,
        )
    assert oversized.status_code == 413
    assert service.indexed_path is None

    invalid_service = FakeRetrievalService()
    invalid_service.index_error = EmptyPDFError("No extractable text.")
    with client_context(invalid_service) as client:
        invalid_pdf = client.post(
            "/api/v1/documents",
            files={"file": ("paper.pdf", b"%PDF-1.7", "application/pdf")},
            headers=client.auth_headers,
        )
    assert invalid_pdf.status_code == 422
    assert invalid_pdf.json()["detail"]["code"] == "invalid_pdf"


def test_search_endpoint_validates_query_and_returns_owned_page_references():
    service = FakeRetrievalService()
    with client_context(service) as client:
        response = client.post(
            "/api/v1/search",
            json={"query": "  useful topic  "},
            headers=client.auth_headers,
        )
        blank_query = client.post(
            "/api/v1/search",
            json={"query": "   "},
            headers=client.auth_headers,
        )

    assert response.status_code == 200
    assert service.query == "useful topic"
    assert service.search_owner_id is not None
    assert response.json() == {
        "query": "useful topic",
        "results": [
            {
                "score": 0.9,
                "document_id": "doc-123",
                "filename": "paper.pdf",
                "page_number": 2,
                "chunk_index": 1,
                "chunk_text": "Relevant paper content.",
            }
        ],
    }
    assert blank_query.status_code == 422


def test_search_endpoint_reports_service_failures():
    service = FakeRetrievalService()
    service.search_error = VectorStoreError("Qdrant unavailable")
    with client_context(service) as client:
        response = client.post(
            "/api/v1/search",
            json={"query": "paper topic"},
            headers=client.auth_headers,
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "retrieval_service_unavailable"
