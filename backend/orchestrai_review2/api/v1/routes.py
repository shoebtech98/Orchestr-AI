from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from ...config import Settings
from ...errors import (
    EmbeddingError,
    EmptyPDFError,
    PDFProcessingError,
    VectorStoreError,
)
from ...models import User
from ...service import RetrievalService
from ..dependencies import get_current_user, get_settings

router = APIRouter()


class DependencyHealth(BaseModel):
    status: Literal["healthy", "unavailable"]


class ApplicationHealth(BaseModel):
    name: str
    status: Literal["healthy"]


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    application: ApplicationHealth
    dependencies: dict[str, DependencyHealth]


class IndexResponse(BaseModel):
    document_id: str
    filename: str
    chunks_indexed: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)

    @field_validator("query")
    @classmethod
    def query_must_not_be_whitespace(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Search query must not be empty.")
        return value


class SearchResult(BaseModel):
    score: float
    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    chunk_text: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


def get_retrieval_service(request: Request) -> RetrievalService:
    return request.app.state.retrieval_service


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


@router.get("/health", response_model=HealthResponse)
def health_check(
    request: Request,
    service: RetrievalService = Depends(get_retrieval_service),
) -> HealthResponse | JSONResponse:
    settings: Settings = request.app.state.settings
    try:
        service.check_qdrant()
    except VectorStoreError:
        health = HealthResponse(
            status="degraded",
            application=ApplicationHealth(name=settings.application_name, status="healthy"),
            dependencies={"qdrant": DependencyHealth(status="unavailable")},
        )
        return JSONResponse(status_code=503, content=health.model_dump())
    return HealthResponse(
        status="healthy",
        application=ApplicationHealth(name=settings.application_name, status="healthy"),
        dependencies={"qdrant": DependencyHealth(status="healthy")},
    )


@router.post("/documents", response_model=IndexResponse, status_code=201)
async def index_document(
    file: UploadFile = File(...),
    service: RetrievalService = Depends(get_retrieval_service),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> IndexResponse:
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not filename or Path(filename).suffix.lower() != ".pdf":
        raise _http_error(415, "unsupported_file_type", "Upload a file with a .pdf extension.")

    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(suffix=".pdf", delete=False) as temporary_file:
            temporary_path = Path(temporary_file.name)
            total_bytes = 0
            while content := await file.read(1024 * 1024):
                total_bytes += len(content)
                if total_bytes > settings.max_upload_bytes:
                    raise _http_error(
                        413,
                        "file_too_large",
                        f"PDF exceeds the {settings.max_upload_bytes}-byte upload limit.",
                    )
                temporary_file.write(content)

        if total_bytes == 0:
            raise _http_error(422, "empty_file", "The uploaded PDF is empty.")

        result = await run_in_threadpool(
            service.index_pdf,
            temporary_path,
            filename,
            str(current_user.id),
        )
        return IndexResponse(**result)
    except (EmptyPDFError, PDFProcessingError, ValueError) as exc:
        raise _http_error(422, "invalid_pdf", str(exc)) from exc
    except (EmbeddingError, VectorStoreError) as exc:
        raise _http_error(503, "retrieval_service_unavailable", str(exc)) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    service: RetrievalService = Depends(get_retrieval_service),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    try:
        results = await run_in_threadpool(service.search, request.query, str(current_user.id))
    except ValueError as exc:
        raise _http_error(422, "invalid_query", str(exc)) from exc
    except (EmbeddingError, VectorStoreError) as exc:
        raise _http_error(503, "retrieval_service_unavailable", str(exc)) from exc
    return SearchResponse(query=request.query, results=results)
