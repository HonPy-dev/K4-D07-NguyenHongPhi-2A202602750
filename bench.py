"""Benchmark runner — Day 7 Lab (K4-L3A).

Reads the cleaned corpus, chunks it with the selected strategy, loads chunks
into EmbeddingStore, runs the group's 5 benchmark queries (with the mandatory
metadata-filter A/B), scores retrieval per docs/SCORING.md, and writes
ket_qua_benchmark.txt.

Only ONE line should differ between team members: the CHUNKER selection below.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.agent import KnowledgeBaseAgent
from src.chunking import RecursiveChunker, SentenceChunker, FixedSizeChunker, compute_similarity
from src.embeddings import OPENAI_EMBEDDING_MODEL, OpenAIEmbedder, _mock_embed
from src.models import Document
from src.store import EmbeddingStore

DATA_DIR = Path("data/utsc-library-services")
OUTPUT_FILE = Path("ket_qua_benchmark.txt")
CHUNK_SIZE = 500

# ─── Chunker selection — each team member switches THIS line ─────────────────
CHUNKER = "fixed"  # "fixed" | "sentence" | "recursive" | "heading" | "semantic"
# ──────────────────────────────────────────────────────────────────────────────

# The 5 group benchmark queries. "marker" is the characteristic string that
# must appear in the retrieved context for the answer to count (content-level
# scoring per docs/SCORING.md, not just doc_id matching).
QUERIES = [
    {
        "id": 1,
        "query": "What are the UTSC Library's regular opening hours from Monday to Friday between September 8 and December 22, 2026?",
        "gold_doc": "utsc-library-hours",
        "marker": "8:00 AM",
        "filter": None,
    },
    {
        "id": 2,
        "query": "As an undergraduate student, how long can I borrow regular library items, and what is my item limit?",
        "gold_doc": "utsc-borrowing-policy",
        "marker": "14 days",
        "filter": None,
    },
    {
        "id": 3,
        "query": "Where should a user return a borrowed laptop from the Technology Loans collection?",
        "gold_doc": "utsc-technology-loans",
        "marker": "returned directly to the Info Desk",
        "filter": None,
    },
    {
        "id": 4,
        "query": "How do I borrow and pick up library items when I cannot visit the library myself due to a disability?",
        "gold_doc": "utsc-borrowing-policy",
        "marker": "application form",
        # A/B: run twice — with and without the mandatory metadata filter.
        # Without the filter, utsc-accessibility-services (audience: all) also
        # talks about proxy borrowing with a DIFFERENT answer (Pickup
        # Authorization Form at the Info Desk), so the two runs must diverge.
        "filter": {"audience": "student"},
    },
    {
        "id": 5,
        "query": "Which service provides a free and secure University of Toronto repository for disseminating and preserving faculty and graduate-student research?",
        "gold_doc": "utsc-research-publishing",
        "marker": "TSpace",
        "filter": None,
    },
]


class HeadingChunker:
    """Custom strategy: split on markdown headings; long sections fall back to
    recursive splitting with the heading re-attached to every sub-piece."""

    def __init__(self, chunk_size: int = 500) -> None:
        self.chunk_size = chunk_size
        self._fallback = RecursiveChunker(chunk_size=chunk_size)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        sections = re.split(r"(?=^#{1,6} )", text, flags=re.M)
        chunks: list[str] = []
        for section in sections:
            section = section.strip()
            if not section:
                continue
            if len(section) <= self.chunk_size:
                chunks.append(section)
                continue
            heading = section.split("\n", 1)[0]
            for piece in self._fallback.chunk(section):
                chunks.append(piece if piece.startswith("#") else f"{heading}\n{piece}")
        return chunks


class SemanticChunker:
    """Custom strategy: embed every sentence, cut between two consecutive
    sentences whose similarity drops below the percentile threshold — chunk
    boundaries follow topic shifts instead of a fixed size. Groups that still
    exceed chunk_size fall back to recursive splitting."""

    def __init__(self, embed_fn, chunk_size: int = 500, percentile: float = 25.0) -> None:
        self.embed_fn = embed_fn
        self.chunk_size = chunk_size
        self.percentile = percentile
        self._fallback = RecursiveChunker(chunk_size=chunk_size)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
        if len(sentences) == 1:
            return [sentences[0]]

        vectors = [self.embed_fn(sentence) for sentence in sentences]
        similarities = [compute_similarity(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
        threshold = sorted(similarities)[max(0, int(len(similarities) * self.percentile / 100) - 1)]

        # Split AFTER sentence i when its link to sentence i+1 is weak.
        groups: list[list[str]] = [[sentences[0]]]
        for i, similarity in enumerate(similarities):
            if similarity < threshold:
                groups.append([sentences[i + 1]])
            else:
                groups[-1].append(sentences[i + 1])

        chunks: list[str] = []
        for group in groups:
            section = " ".join(group)
            if len(section) <= self.chunk_size:
                chunks.append(section)
            else:
                chunks.extend(self._fallback.chunk(section))
        return chunks


def make_chunker(embed_fn=None) -> object:
    if CHUNKER == "fixed":
        return FixedSizeChunker(chunk_size=CHUNK_SIZE, overlap=50)
    if CHUNKER == "sentence":
        return SentenceChunker(max_sentences_per_chunk=5)
    if CHUNKER == "heading":
        return HeadingChunker(chunk_size=CHUNK_SIZE)
    if CHUNKER == "semantic":
        return SemanticChunker(embed_fn=embed_fn, chunk_size=CHUNK_SIZE)
    return RecursiveChunker(chunk_size=CHUNK_SIZE)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}, text
    metadata = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata, text[match.end() :]


def cached_embedder(embed_fn):
    """Wrap an embedder with a content-hash cache so re-runs cost nothing."""
    cache: dict[str, list[float]] = {}

    def embed(text: str) -> list[float]:
        key = hashlib.md5(text.encode()).hexdigest()
        if key not in cache:
            cache[key] = embed_fn(text)
        return cache[key]

    return embed


def make_embedder():
    provider = os.getenv("EMBEDDING_PROVIDER", "mock").strip().lower()
    if provider == "openai":
        try:
            embedder = OpenAIEmbedder(model_name=os.getenv("OPENAI_EMBEDDING_MODEL", OPENAI_EMBEDDING_MODEL))
        except Exception as error:
            print(f"[warn] OpenAI embedder unavailable ({error}); falling back to mock", file=sys.stderr)
            return _mock_embed
    else:
        return _mock_embed
    return cached_embedder(embedder)


def make_llm_fn():
    """LLM via OpenRouter chat completions (same key, OPENAI_BASE_URL env)."""
    model = os.getenv("OPENROUTER_LLM_MODEL", "openai/gpt-4o-mini")
    try:
        from openai import OpenAI

        client = OpenAI()  # uses OPENAI_API_KEY + OPENAI_BASE_URL from .env
    except Exception as error:
        print(f"[warn] LLM unavailable ({error}); agent answers will be skipped", file=sys.stderr)
        return None

    def llm_fn(prompt: str) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return response.choices[0].message.content or ""

    print(f"LLM backend: OpenRouter {model}")
    return llm_fn


def load_chunk_documents(embed_fn=None) -> list[Document]:
    chunker = make_chunker(embed_fn)
    documents: list[Document] = []
    for path in sorted(DATA_DIR.glob("*.md")):
        metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        for index, chunk in enumerate(chunker.chunk(body)):
            documents.append(
                Document(
                    id=f"{path.stem}#{index}",
                    content=chunk,
                    metadata={**metadata, "doc_id": path.stem},
                )
            )
    return documents


def score_result(result: dict, gold_doc: str, marker: str) -> int:
    top_ids = [chunk["metadata"]["doc_id"] for chunk in result["top3"]]
    context = "\n".join(chunk["content"] for chunk in result["top3"])
    marker_found = marker.lower() in context.lower()
    if top_ids and top_ids[0] == gold_doc and marker_found:
        return 2
    if gold_doc in top_ids and marker_found:
        return 1
    return 0


def main() -> int:
    # override=True: the machine may carry a stale global OPENAI_API_KEY;
    # our .env (gitignored) must win for the OpenRouter endpoints to work.
    load_dotenv(override=True)
    lines: list[str] = []

    def out(text: str = "") -> None:
        print(text)
        lines.append(text)

    out(f"=== UTSC Library benchmark — chunker: {CHUNKER}, chunk_size: {CHUNK_SIZE} ===")

    embed_fn = make_embedder()
    backend = getattr(embed_fn, "_backend_name", None) or (
        "openai/text-embedding-3-small (cached)" if os.getenv("EMBEDDING_PROVIDER") == "openai" else "mock"
    )
    out(f"Embedding backend: {backend}")

    documents = load_chunk_documents(embed_fn)
    out(f"Chunks loaded: {len(documents)} from {DATA_DIR}")

    store = EmbeddingStore(collection_name="bench", embedding_fn=embed_fn)
    store.add_documents(documents)

    llm_fn = make_llm_fn()
    agent = KnowledgeBaseAgent(store=store, llm_fn=llm_fn) if llm_fn else None

    total = 0
    max_score = 0
    for spec in QUERIES:
        variants = [("with filter", spec["filter"]), ("no filter", None)] if spec["filter"] else [("no filter", None)]
        for label, metadata_filter in variants:
            top3 = store.search_with_filter(spec["query"], top_k=3, metadata_filter=metadata_filter)
            result = {"top3": top3}
            score = score_result(result, spec["gold_doc"], spec["marker"])
            out(f"\n--- Q{spec['id']} ({label}) | gold: {spec['gold_doc']} | score: {score}/2")
            for rank, chunk in enumerate(top3, start=1):
                preview = chunk["content"][:90].replace("\n", " ")
                out(f"  {rank}. [{chunk['metadata']['doc_id']}] score={chunk['score']:.3f} :: {preview}...")
            if label == "with filter" or not spec["filter"]:
                total += score
                max_score += 2
            if agent and label == "no filter":
                answer = agent.answer(spec["query"], top_k=3)
                out(f"  Agent answer: {answer.strip()[:280]}")

    out(f"\n=== TOTAL: {total}/{max_score} (strategy: {CHUNKER}) ===")
    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
