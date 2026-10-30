class PipelineError(Exception):
    """Base class for expected pipeline failures."""


class EmptyPDFError(PipelineError):
    """Raised when a PDF contains no extractable text."""


class PDFProcessingError(PipelineError):
    """Raised when a PDF cannot be read or processed."""


class EmbeddingError(PipelineError):
    """Raised when the embedding model cannot load or encode text."""


class VectorStoreError(PipelineError):
    """Raised when Qdrant cannot complete an operation."""
