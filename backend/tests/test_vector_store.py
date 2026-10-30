from types import SimpleNamespace

from orchestrai_review2.vector_store import QdrantStore


class FakeQdrantClient:
    def __init__(self):
        self.upserted_points = None
        self.query_options = None

    def upsert(self, **kwargs):
        self.upserted_points = kwargs["points"]

    def get_collections(self):
        return SimpleNamespace(
            collections=[SimpleNamespace(name="orchestrai_papers")]
        )

    def query_points(self, **kwargs):
        self.query_options = kwargs
        return SimpleNamespace(points=[])


def build_store():
    store = QdrantStore.__new__(QdrantStore)
    store.collection_name = "orchestrai_papers"
    store.client = FakeQdrantClient()
    return store


def test_qdrant_points_have_user_scoped_ids_and_owner_payload():
    store = build_store()
    document_id = "63afc770-d429-4eab-88bc-aed041a6f873"
    records = [
        {
            "chunk_index": 0,
            "chunk_text": "private text",
            "owner_id": "user-1",
        }
    ]

    store.upsert(document_id, records, [[0.1, 0.2]], owner_id="user-1")
    first_point_id = store.client.upserted_points[0].id
    first_owner = store.client.upserted_points[0].payload["owner_id"]
    store.upsert(document_id, records, [[0.1, 0.2]], owner_id="user-2")
    second_point_id = store.client.upserted_points[0].id
    second_owner = store.client.upserted_points[0].payload["owner_id"]

    assert first_point_id != second_point_id
    assert first_owner == "user-1"
    assert second_owner == "user-2"


def test_qdrant_search_filters_by_owner_and_cli_search_remains_unfiltered():
    store = build_store()

    store.search([0.1, 0.2], owner_id="user-1")
    scoped_filter = store.client.query_options["query_filter"]
    assert scoped_filter.must[0].key == "owner_id"
    assert scoped_filter.must[0].match.value == "user-1"

    store.search([0.1, 0.2])
    assert "query_filter" not in store.client.query_options
