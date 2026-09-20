from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self._store = store
        self._llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        chunks = self._store.search(question, top_k=top_k)
        if chunks:
            context = "\n\n".join(
                f"[{index + 1}] {chunk['content']}" for index, chunk in enumerate(chunks)
            )
        else:
            context = "(no matching documents found)"
        prompt = (
            "You are a helpful assistant. Answer the question using only the "
            "context below. If the context does not contain the answer, say so.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )
        return self._llm_fn(prompt)
