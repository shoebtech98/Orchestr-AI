from .errors import EmbeddingError


class EmbeddingModel:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)
            get_dimension = getattr(self._model, "get_embedding_dimension", None)
            if get_dimension is None:
                get_dimension = self._model.get_sentence_embedding_dimension
            self.dimension = get_dimension()
            if not self.dimension:
                raise ValueError("The model did not report an embedding dimension.")
        except Exception as exc:
            raise EmbeddingError(
                f"Could not load embedding model '{model_name}': {exc}"
            ) from exc

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self._model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return vectors.tolist()
        except Exception as exc:
            raise EmbeddingError(f"Could not generate embeddings: {exc}") from exc
