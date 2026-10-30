import uuid

from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from .errors import VectorStoreError


class QdrantStore:
    def __init__(self, url: str, collection_name: str):
        self.collection_name = collection_name
        self.client = QdrantClient(url=url)

    def check_connection(self) -> None:
        try:
            self.client.get_collections()
        except Exception as exc:
            raise VectorStoreError(f"Could not connect to Qdrant: {exc}") from exc

    def close(self) -> None:
        self.client.close()

    def ensure_collection(self, vector_size: int) -> None:
        try:
            collection_names = {
                collection.name for collection in self.client.get_collections().collections
            }
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
                return

            collection = self.client.get_collection(self.collection_name)
            config = collection.config.params.vectors
            if not isinstance(config, models.VectorParams):
                raise VectorStoreError(
                    f"Collection '{self.collection_name}' uses named vectors; "
                    "this prototype expects a single unnamed vector."
                )
            if config.size != vector_size or config.distance != Distance.COSINE:
                raise VectorStoreError(
                    f"Collection '{self.collection_name}' has incompatible vectors "
                    f"(size={config.size}, distance={config.distance}); expected "
                    f"(size={vector_size}, distance=Cosine). The collection was not changed."
                )
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(f"Could not prepare Qdrant collection: {exc}") from exc

    def upsert(
        self,
        document_id: str,
        records: list[dict],
        vectors: list[list[float]],
        owner_id: str | None = None,
    ) -> None:
        namespace = uuid.UUID(document_id)
        if owner_id is not None:
            namespace = uuid.uuid5(uuid.NAMESPACE_URL, f"orchestrai-user:{owner_id}:{document_id}")
        points = [
            PointStruct(
                id=str(uuid.uuid5(namespace, str(record["chunk_index"]))),
                vector=vector,
                payload={**record, "owner_id": owner_id} if owner_id is not None else record,
            )
            for record, vector in zip(records, vectors, strict=True)
        ]
        try:
            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        except Exception as exc:
            raise VectorStoreError(f"Could not store document chunks in Qdrant: {exc}") from exc

    def search(
        self,
        vector: list[float],
        limit: int = 5,
        owner_id: str | None = None,
    ) -> list[dict]:
        try:
            collection_names = {
                collection.name for collection in self.client.get_collections().collections
            }
            if self.collection_name not in collection_names:
                raise VectorStoreError(
                    f"Collection '{self.collection_name}' does not exist; index a PDF first."
                )
            query_options = {}
            if owner_id is not None:
                query_options["query_filter"] = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="owner_id",
                            match=models.MatchValue(value=owner_id),
                        )
                    ]
                )
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                limit=limit,
                with_payload=True,
                **query_options,
            )
            return [
                {"score": point.score, **(point.payload or {})}
                for point in response.points
            ]
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(f"Could not search Qdrant: {exc}") from exc
