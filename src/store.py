from __future__ import annotations

from typing import Any, Callable

from .chunking import _dot
from .embeddings import _mock_embed
from .models import Document


class EmbeddingStore:
    """
    An in-memory vector store for text chunks.

    Embeddings are produced by the injected embedding_fn (mock for tests,
    real backends for the benchmark). Vectors are compared with dot product,
    which equals cosine similarity when embeddings are normalized.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        embedding_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._embedding_fn = embedding_fn or _mock_embed
        self._collection_name = collection_name
        self._use_chroma = False
        self._store: list[dict[str, Any]] = []
        self._collection = None
        self._next_index = 0

    def _make_record(self, doc: Document) -> dict[str, Any]:
        return {
            "id": doc.id,
            "content": doc.content,
            "embedding": self._embedding_fn(doc.content),
            "metadata": dict(doc.metadata),
        }

    def _search_records(self, query: str, records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        if top_k <= 0 or not records:
            return []
        query_vector = self._embedding_fn(query)
        scored = [
            {"id": record["id"], "content": record["content"], "metadata": record["metadata"],
             "score": _dot(query_vector, record["embedding"])}
            for record in records
        ]
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def add_documents(self, docs: list[Document]) -> None:
        """
        Embed each document's content and store it.

        One Document becomes exactly one stored record — chunking happens
        outside this layer (each chunk should be its own Document).
        """
        for doc in docs:
            self._store.append(self._make_record(doc))

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Find the top_k most similar documents to query.

        For in-memory: compute dot product of query embedding vs all stored embeddings.
        """
        return self._search_records(query, self._store, top_k)

    def get_collection_size(self) -> int:
        """Return the total number of stored chunks."""
        return len(self._store)

    def search_with_filter(self, query: str, top_k: int = 3, metadata_filter: dict = None) -> list[dict]:
        """
        Search with optional metadata pre-filtering.

        First filter stored chunks by metadata_filter, then run similarity search —
        filtering after the search would let off-topic chunks crowd out the
        relevant ones inside top_k.
        """
        if not metadata_filter:
            return self._search_records(query, self._store, top_k)
        candidates = [
            record for record in self._store
            if all(record["metadata"].get(key) == value for key, value in metadata_filter.items())
        ]
        return self._search_records(query, candidates, top_k)

    def delete_document(self, doc_id: str) -> bool:
        """
        Remove all chunks belonging to a document.

        A chunk belongs to the document when metadata['doc_id'] matches, or
        when the chunk's own id matches (single-Document records added
        without metadata). Returns True if any chunks were removed.
        """
        before = len(self._store)
        self._store = [
            record for record in self._store
            if record["metadata"].get("doc_id") != doc_id and record["id"] != doc_id
        ]
        return len(self._store) < before
