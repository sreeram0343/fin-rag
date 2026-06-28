import re
import math
from typing import Any, Dict, List, Optional, Set

import structlog

from finrag.db.document_repository import DocumentRepository
from finrag.db.chunk_repository import ChunkRepository
from finrag.db.vector.client import BaseVectorClient
from finrag.indexer.embeddings import BaseEmbeddingProvider
from finrag.retriever.base import BaseRetriever

logger = structlog.get_logger(__name__)


class BM25:
    """Lightweight in-memory BM25 index for sparse search over a subset of chunks."""

    def __init__(self, corpus: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.num_docs = len(corpus)
        self.doc_lengths: List[int] = []
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}

        total_length = 0
        for doc in corpus:
            tokens = self._tokenize(doc.get("text", ""))
            self.doc_lengths.append(len(tokens))
            total_length += len(tokens)

            freqs: Dict[str, int] = {}
            for token in tokens:
                freqs[token] = freqs.get(token, 0) + 1
            self.doc_freqs.append(freqs)

        self.avg_doc_len = total_length / self.num_docs if self.num_docs > 0 else 0.0

        # Calculate IDF for each unique token in corpus
        all_tokens: Set[str] = set()
        for freqs in self.doc_freqs:
            all_tokens.update(freqs.keys())

        for token in all_tokens:
            doc_count = sum(1 for freqs in self.doc_freqs if token in freqs)
            # Lucene-style BM25 IDF formula
            self.idf[token] = math.log(1.0 + (self.num_docs - doc_count + 0.5) / (doc_count + 0.5))

    def _tokenize(self, text: str) -> List[str]:
        """Convert text to lowercase alphanumeric word tokens."""
        return [w.lower() for w in re.findall(r"\b\w+\b", text)]

    def score(self, query: str) -> List[float]:
        """Score all documents in corpus against the query string."""
        query_tokens = self._tokenize(query)
        scores: List[float] = []

        for i in range(self.num_docs):
            doc_len = self.doc_lengths[i]
            freqs = self.doc_freqs[i]
            score = 0.0

            for token in query_tokens:
                if token not in self.idf:
                    continue
                tf = freqs.get(token, 0)
                # BM25 TF shaping
                tf_part = (tf * (self.k1 + 1.0)) / (
                    tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len if self.avg_doc_len > 0 else 1.0))
                )
                score += self.idf[token] * tf_part

            scores.append(score)

        return scores


class HybridRetriever(BaseRetriever):
    """Hybrid dense-sparse retrieval orchestrator.

    Queries Qdrant for semantic match candidates, uses a custom BM25 index on PostgreSQL chunks for
    keyword relevance, merges both lists using Reciprocal Rank Fusion (RRF), and refines with an optional reranker.
    """

    def __init__(
        self,
        vector_client: BaseVectorClient,
        embedding_provider: BaseEmbeddingProvider,
        doc_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        reranker: Optional[Any] = None,
        rrf_k: int = 60,
    ) -> None:
        self.vector_client = vector_client
        self.embedding_provider = embedding_provider
        self.doc_repo = doc_repo
        self.chunk_repo = chunk_repo
        self.reranker = reranker
        self.rrf_k = rrf_k

    async def retrieve(
        self,
        query: str,
        ticker: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Run hybrid search, merge via RRF, and return top_k candidates."""
        logger.info("Executing hybrid search", query=query, ticker=ticker, filters=filters, top_k=top_k)

        # 1. Filter documents based on ticker and optional period/year filters
        docs = await self.doc_repo.list_all(ticker=ticker)
        if not docs:
            logger.info("No documents found for ticker", ticker=ticker)
            return []

        # Apply year and document_type/period filters
        allowed_doc_ids = []
        for doc in docs:
            keep = True
            if filters:
                if "years" in filters and doc.year not in filters["years"]:
                    keep = False
                if "document_types" in filters:
                    # Let's map document types: Q1-Q4, FY, H1-H2 to period
                    # If any type matches doc.period, keep it
                    types = [t.strip().upper() for t in filters["document_types"]]
                    if doc.period not in types and doc.period != "FY":
                        # Also support mapping "10-Q" to Q1, Q2, Q3 and "10-K" to FY
                        is_10q = "10-Q" in types and doc.period in ["Q1", "Q2", "Q3"]
                        is_10k = "10-K" in types and doc.period == "FY"
                        if not (is_10q or is_10k):
                            keep = False
            if keep:
                allowed_doc_ids.append(doc.id)

        if not allowed_doc_ids:
            logger.info("No documents matched the query filters", filters=filters)
            return []

        # 2. Fetch all allowed chunks from DB to build the BM25 sparse index
        all_chunks = []
        for doc_id in allowed_doc_ids:
            chunks = await self.chunk_repo.get_by_document_id(doc_id)
            all_chunks.extend(chunks)

        if not all_chunks:
            logger.info("No chunks found in database for the filtered documents")
            return []

        # Map chunks by ID for quick lookups
        chunks_map = {chunk.id: chunk for chunk in all_chunks}

        # 3. Dense Retrieval
        dense_results: List[Dict[str, Any]] = []
        try:
            query_vector = self.embedding_provider.embed_single(query)
            # Use vector client search
            # Filter dense results using Qdrant filters if possible, or post-filter in Python
            qdrant_filters = {"ticker": ticker}
            # Search a larger pool so we have enough candidate overlap
            raw_dense_hits = self.vector_client.search(
                query_vector=query_vector,
                top_k=top_k * 4,
                filters=qdrant_filters,
            )
            # Filter hits to ensure they are in the allowed document IDs
            dense_results = [
                hit for hit in raw_dense_hits
                if hit.get("payload", {}).get("document_id") in allowed_doc_ids
            ]
        except Exception as e:
            logger.exception("Dense retrieval failed. Continuing with sparse-only search.", error=str(e))

        # 4. Sparse Retrieval (BM25)
        sparse_corpus = [
            {"id": chunk.id, "text": chunk.chunk_text}
            for chunk in all_chunks
        ]
        bm25 = BM25(sparse_corpus)
        bm25_scores = bm25.score(query)

        # Sort sparse candidates
        sparse_candidates = []
        for doc_idx, score in enumerate(bm25_scores):
            if score > 0.0:
                sparse_candidates.append({
                    "id": sparse_corpus[doc_idx]["id"],
                    "score": score
                })
        sparse_candidates.sort(key=lambda x: x["score"], reverse=True)
        # Limit to top pool
        sparse_results = sparse_candidates[:top_k * 4]

        # 5. Reciprocal Rank Fusion (RRF)
        rrf_scores: Dict[str, float] = {}

        # Merge dense ranks
        for rank_idx, hit in enumerate(dense_results):
            chunk_id = hit["id"]
            # 1-based rank
            rank = rank_idx + 1
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (self.rrf_k + rank))

        # Merge sparse ranks
        for rank_idx, hit in enumerate(sparse_results):
            chunk_id = hit["id"]
            rank = rank_idx + 1
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (self.rrf_k + rank))

        # Sort by RRF score descending
        sorted_rrf = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        top_candidates = sorted_rrf[:top_k * 2]

        # Construct candidate payloads
        candidates: List[Dict[str, Any]] = []
        for chunk_id, rrf_score in top_candidates:
            chunk = chunks_map.get(chunk_id)
            if chunk:
                # Resolve coordinate arrays if stored as JSON list or other representation
                bbox = chunk.bounding_box
                if isinstance(bbox, str):
                    import json
                    try:
                        bbox = json.loads(bbox)
                    except Exception:
                        bbox = [0, 0, 0, 0]

                candidates.append({
                    "id": chunk.id,
                    "document_id": chunk.document_id,
                    "page_number": chunk.page_number,
                    "bounding_box": bbox,
                    "chunk_text": chunk.chunk_text,
                    "chunk_type": chunk.chunk_type,
                    "parent_header": chunk.parent_header,
                    "score": rrf_score,
                })

        # 6. Reranking (optional)
        if self.reranker and candidates:
            candidates = self.reranker.rerank(query, candidates, top_k=top_k)
        else:
            candidates = candidates[:top_k]

        logger.info("Hybrid search completed", total_retrieved=len(candidates))
        return candidates
