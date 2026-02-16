"""
Hybrid Search - Combines semantic search with keyword-based search for better results.

This module implements:
- BM25 keyword search
- Semantic vector search
- Reciprocal Rank Fusion (RRF) for combining results
- Query expansion and rewriting
"""

import asyncio
import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class SearchMode(str, Enum):
    """Search mode for hybrid search."""
    SEMANTIC_ONLY = "semantic_only"
    KEYWORD_ONLY = "keyword_only"
    HYBRID = "hybrid"
    AUTO = "auto"  # Automatically choose based on query


class FusionMethod(str, Enum):
    """Method for fusing search results."""
    RRF = "rrf"  # Reciprocal Rank Fusion
    WEIGHTED_SUM = "weighted_sum"
    MAX_SCORE = "max_score"
    INTERLEAVE = "interleave"


@dataclass
class SearchResult:
    """Individual search result."""
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"  # "semantic" or "keyword"
    chunk_index: Optional[int] = None
    highlights: list[str] = field(default_factory=list)


@dataclass
class HybridSearchResult:
    """Combined result from hybrid search."""
    results: list[SearchResult]
    query: str
    mode_used: SearchMode
    semantic_count: int
    keyword_count: int
    fusion_method: FusionMethod
    total_candidates: int
    execution_time_ms: float


class BM25Index:
    """
    BM25 (Best Matching 25) keyword search index.

    Implements the Okapi BM25 ranking function for keyword-based search.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 index.

        Args:
            k1: Term frequency saturation parameter (default 1.5)
            b: Length normalization parameter (default 0.75)
        """
        self.k1 = k1
        self.b = b
        self.documents: dict[str, str] = {}  # doc_id -> content
        self.doc_lengths: dict[str, int] = {}
        self.avg_doc_length: float = 0.0
        self.term_frequencies: dict[str, dict[str, int]] = {}  # term -> {doc_id: freq}
        self.document_frequencies: dict[str, int] = {}  # term -> num_docs_containing
        self.total_docs: int = 0
        self._metadata: dict[str, dict] = {}

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into terms."""
        # Simple tokenization - lowercase and split on non-alphanumeric
        text = text.lower()
        tokens = re.findall(r'\b[a-z0-9]+\b', text)
        # Remove very short tokens and stopwords
        stopwords = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
            'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
            'that', 'the', 'to', 'was', 'were', 'will', 'with'
        }
        return [t for t in tokens if len(t) > 1 and t not in stopwords]

    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[dict] = None
    ) -> None:
        """Add a document to the index."""
        tokens = self._tokenize(content)
        self.documents[doc_id] = content
        self.doc_lengths[doc_id] = len(tokens)
        self._metadata[doc_id] = metadata or {}

        # Update term frequencies
        term_counts = defaultdict(int)
        for token in tokens:
            term_counts[token] += 1

        for term, count in term_counts.items():
            if term not in self.term_frequencies:
                self.term_frequencies[term] = {}
                self.document_frequencies[term] = 0

            # Check if doc_id is new for this term BEFORE adding
            if doc_id not in self.term_frequencies[term]:
                self.document_frequencies[term] += 1

            # Add the term frequency for this doc
            self.term_frequencies[term][doc_id] = count

        self.total_docs += 1
        self.avg_doc_length = sum(self.doc_lengths.values()) / self.total_docs

    def add_documents(
        self,
        documents: list[tuple[str, str, Optional[dict]]]
    ) -> None:
        """Add multiple documents to the index."""
        for doc_id, content, metadata in documents:
            self.add_document(doc_id, content, metadata)

    def _idf(self, term: str) -> float:
        """Calculate Inverse Document Frequency for a term."""
        if term not in self.document_frequencies:
            return 0.0

        n = self.total_docs
        df = self.document_frequencies[term]

        # Standard BM25 IDF formula
        return math.log((n - df + 0.5) / (df + 0.5) + 1.0)

    def _score_document(self, doc_id: str, query_terms: list[str]) -> float:
        """Calculate BM25 score for a document given query terms."""
        score = 0.0
        doc_length = self.doc_lengths.get(doc_id, 0)

        if doc_length == 0:
            return 0.0

        for term in query_terms:
            if term not in self.term_frequencies:
                continue

            tf = self.term_frequencies[term].get(doc_id, 0)
            if tf == 0:
                continue

            idf = self._idf(term)

            # BM25 scoring formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / self.avg_doc_length)
            score += idf * numerator / denominator

        return score

    def _matches_where_filter(self, doc_id: str, where: dict) -> bool:
        """
        Check if a document matches the metadata filter.

        Supports simple equality filters: {"category": "academic"}
        Also supports $eq operator: {"category": {"$eq": "academic"}}

        Args:
            doc_id: Document ID to check
            where: Metadata filter dict

        Returns:
            True if document matches filter, False otherwise
        """
        metadata = self._metadata.get(doc_id, {})

        for key, value in where.items():
            doc_value = metadata.get(key)

            # Handle operator syntax: {"field": {"$eq": "value"}}
            if isinstance(value, dict):
                if "$eq" in value:
                    if doc_value != value["$eq"]:
                        return False
                elif "$ne" in value:
                    if doc_value == value["$ne"]:
                        return False
                elif "$in" in value:
                    if doc_value not in value["$in"]:
                        return False
                elif "$nin" in value:
                    if doc_value in value["$nin"]:
                        return False
                # Unknown operator - skip
            else:
                # Simple equality: {"field": "value"}
                if doc_value != value:
                    return False

        return True

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
        where: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Search the index for documents matching the query.

        Args:
            query: Search query
            top_k: Maximum number of results to return
            min_score: Minimum score threshold
            where: Optional metadata filter (e.g., {"category": "academic"})

        Returns:
            List of SearchResult objects
        """
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # Score all documents, applying metadata filter if provided
        scores: list[tuple[str, float]] = []
        for doc_id in self.documents:
            # Apply metadata filter if provided
            if where and not self._matches_where_filter(doc_id, where):
                continue

            score = self._score_document(doc_id, query_terms)
            if score > min_score:
                scores.append((doc_id, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        # Create results
        results = []
        for doc_id, score in scores[:top_k]:
            # Extract highlights (sentences containing query terms)
            highlights = self._extract_highlights(doc_id, query_terms)

            results.append(SearchResult(
                document_id=doc_id,
                content=self.documents[doc_id],
                score=score,
                metadata=self._metadata.get(doc_id, {}),
                source="keyword",
                highlights=highlights,
            ))

        return results

    def _extract_highlights(
        self,
        doc_id: str,
        query_terms: list[str],
        max_highlights: int = 3
    ) -> list[str]:
        """Extract sentence highlights containing query terms."""
        content = self.documents.get(doc_id, "")
        sentences = re.split(r'[.!?]+', content)
        highlights = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_lower = sentence.lower()
            if any(term in sentence_lower for term in query_terms):
                highlights.append(sentence[:200])  # Limit highlight length

            if len(highlights) >= max_highlights:
                break

        return highlights

    def clear(self) -> None:
        """Clear the index."""
        self.documents.clear()
        self.doc_lengths.clear()
        self.term_frequencies.clear()
        self.document_frequencies.clear()
        self._metadata.clear()
        self.total_docs = 0
        self.avg_doc_length = 0.0


class HybridSearch:
    """
    Hybrid search combining semantic and keyword search.

    Uses Reciprocal Rank Fusion (RRF) or other methods to combine
    results from vector similarity search and BM25 keyword search.
    """

    def __init__(
        self,
        semantic_search_fn: Optional[Callable] = None,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        rrf_k: int = 60,
    ):
        """
        Initialize hybrid search.

        Args:
            semantic_search_fn: Async function for semantic search
            semantic_weight: Weight for semantic search results (0-1)
            keyword_weight: Weight for keyword search results (0-1)
            rrf_k: RRF constant (typically 60)
        """
        self.semantic_search_fn = semantic_search_fn
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.rrf_k = rrf_k
        self.bm25_index = BM25Index()
        self._collection_indexes: dict[str, BM25Index] = {}

    def get_or_create_index(self, collection: str) -> BM25Index:
        """Get or create a BM25 index for a collection."""
        if collection not in self._collection_indexes:
            self._collection_indexes[collection] = BM25Index()
        return self._collection_indexes[collection]

    def index_document(
        self,
        doc_id: str,
        content: str,
        collection: str = "default",
        metadata: Optional[dict] = None,
    ) -> None:
        """Index a document for keyword search."""
        index = self.get_or_create_index(collection)
        index.add_document(doc_id, content, metadata)

    def index_documents(
        self,
        documents: list[dict],
        collection: str = "default",
    ) -> int:
        """
        Index multiple documents.

        Args:
            documents: List of dicts with 'id', 'content', and optional 'metadata'
            collection: Collection name

        Returns:
            Number of documents indexed
        """
        index = self.get_or_create_index(collection)
        count = 0

        for doc in documents:
            doc_id = doc.get("id", str(count))
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})

            if content:
                index.add_document(doc_id, content, metadata)
                count += 1

        logger.info(f"Indexed {count} documents in collection '{collection}'")
        return count

    async def search(
        self,
        query: str,
        collection: str = "default",
        top_k: int = 10,
        mode: SearchMode = SearchMode.AUTO,
        fusion_method: FusionMethod = FusionMethod.RRF,
        semantic_params: Optional[dict] = None,
    ) -> HybridSearchResult:
        """
        Perform hybrid search combining semantic and keyword search.

        Args:
            query: Search query
            collection: Collection to search
            top_k: Number of results to return
            mode: Search mode (semantic, keyword, hybrid, auto)
            fusion_method: Method for combining results
            semantic_params: Additional parameters for semantic search

        Returns:
            HybridSearchResult with combined results
        """
        import time
        start_time = time.time()

        # Determine search mode
        actual_mode = self._determine_mode(query, mode)

        semantic_results: list[SearchResult] = []
        keyword_results: list[SearchResult] = []

        # Perform searches based on mode
        if actual_mode in (SearchMode.SEMANTIC_ONLY, SearchMode.HYBRID):
            if self.semantic_search_fn:
                semantic_results = await self._semantic_search(
                    query, collection, top_k * 2, semantic_params
                )

        if actual_mode in (SearchMode.KEYWORD_ONLY, SearchMode.HYBRID):
            keyword_results = self._keyword_search(query, collection, top_k * 2)

        # Combine results
        if actual_mode == SearchMode.SEMANTIC_ONLY:
            combined = semantic_results[:top_k]
        elif actual_mode == SearchMode.KEYWORD_ONLY:
            combined = keyword_results[:top_k]
        else:
            combined = self._fuse_results(
                semantic_results,
                keyword_results,
                fusion_method,
                top_k,
            )

        execution_time = (time.time() - start_time) * 1000

        return HybridSearchResult(
            results=combined,
            query=query,
            mode_used=actual_mode,
            semantic_count=len(semantic_results),
            keyword_count=len(keyword_results),
            fusion_method=fusion_method,
            total_candidates=len(semantic_results) + len(keyword_results),
            execution_time_ms=execution_time,
        )

    def _determine_mode(self, query: str, requested_mode: SearchMode) -> SearchMode:
        """Determine the best search mode for a query."""
        if requested_mode != SearchMode.AUTO:
            return requested_mode

        # Heuristics for auto mode selection
        query_lower = query.lower()

        # Use keyword search for specific patterns
        keyword_patterns = [
            r'^".*"$',  # Exact phrase in quotes
            r'\b(CVE-\d{4}-\d+)\b',  # CVE IDs
            r'\b(CWE-\d+)\b',  # CWE IDs
            r'^[A-Z]{2,}-\d+$',  # Issue/ticket IDs
        ]

        for pattern in keyword_patterns:
            if re.search(pattern, query):
                return SearchMode.KEYWORD_ONLY

        # Use semantic for natural language questions
        question_words = ['what', 'why', 'how', 'when', 'where', 'which', 'who']
        if any(query_lower.startswith(w) for w in question_words):
            return SearchMode.HYBRID

        # Use semantic for conceptual queries
        conceptual_patterns = [
            r'\b(similar|related|like|about|regarding)\b',
            r'\b(explain|describe|overview|summary)\b',
        ]
        for pattern in conceptual_patterns:
            if re.search(pattern, query_lower):
                return SearchMode.SEMANTIC_ONLY

        # Default to hybrid
        return SearchMode.HYBRID

    async def _semantic_search(
        self,
        query: str,
        collection: str,
        top_k: int,
        params: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Perform semantic search using the provided function."""
        if not self.semantic_search_fn:
            return []

        try:
            params = params or {}
            raw_results = await self.semantic_search_fn(
                query=query,
                collection=collection,
                n_results=top_k,
                **params,
            )

            # Convert to SearchResult format
            results = []
            documents = raw_results.get("documents", [[]])[0]
            metadatas = raw_results.get("metadatas", [[]])[0]
            distances = raw_results.get("distances", [[]])[0]
            ids = raw_results.get("ids", [[]])[0]

            for i, (doc, meta, dist, doc_id) in enumerate(
                zip(documents, metadatas, distances, ids)
            ):
                # Convert distance to similarity score (1 - distance for cosine)
                score = 1.0 - dist if dist <= 1.0 else 1.0 / (1.0 + dist)

                results.append(SearchResult(
                    document_id=doc_id,
                    content=doc,
                    score=score,
                    metadata=meta or {},
                    source="semantic",
                ))

            return results

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def _keyword_search(
        self,
        query: str,
        collection: str,
        top_k: int,
    ) -> list[SearchResult]:
        """Perform BM25 keyword search."""
        index = self._collection_indexes.get(collection, self.bm25_index)
        return index.search(query, top_k)

    def _fuse_results(
        self,
        semantic_results: list[SearchResult],
        keyword_results: list[SearchResult],
        method: FusionMethod,
        top_k: int,
    ) -> list[SearchResult]:
        """Fuse results from semantic and keyword search."""
        if method == FusionMethod.RRF:
            return self._rrf_fusion(semantic_results, keyword_results, top_k)
        elif method == FusionMethod.WEIGHTED_SUM:
            return self._weighted_sum_fusion(semantic_results, keyword_results, top_k)
        elif method == FusionMethod.MAX_SCORE:
            return self._max_score_fusion(semantic_results, keyword_results, top_k)
        elif method == FusionMethod.INTERLEAVE:
            return self._interleave_fusion(semantic_results, keyword_results, top_k)
        else:
            return self._rrf_fusion(semantic_results, keyword_results, top_k)

    def _rrf_fusion(
        self,
        semantic_results: list[SearchResult],
        keyword_results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """
        Reciprocal Rank Fusion (RRF) for combining ranked lists.

        RRF score = sum(1 / (k + rank)) for each list where document appears.
        """
        rrf_scores: dict[str, float] = defaultdict(float)
        doc_map: dict[str, SearchResult] = {}

        # Score semantic results
        for rank, result in enumerate(semantic_results, 1):
            rrf_scores[result.document_id] += self.semantic_weight / (self.rrf_k + rank)
            doc_map[result.document_id] = result

        # Score keyword results
        for rank, result in enumerate(keyword_results, 1):
            rrf_scores[result.document_id] += self.keyword_weight / (self.rrf_k + rank)
            if result.document_id not in doc_map:
                doc_map[result.document_id] = result
            else:
                # Merge highlights from keyword search
                doc_map[result.document_id].highlights.extend(result.highlights)

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # Create final results
        results = []
        for doc_id in sorted_ids[:top_k]:
            result = doc_map[doc_id]
            result.score = rrf_scores[doc_id]
            results.append(result)

        return results

    def _weighted_sum_fusion(
        self,
        semantic_results: list[SearchResult],
        keyword_results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Combine results using weighted sum of normalized scores."""
        # Normalize scores
        max_semantic = max((r.score for r in semantic_results), default=1.0)
        max_keyword = max((r.score for r in keyword_results), default=1.0)

        combined_scores: dict[str, float] = defaultdict(float)
        doc_map: dict[str, SearchResult] = {}

        for result in semantic_results:
            norm_score = result.score / max_semantic if max_semantic > 0 else 0
            combined_scores[result.document_id] += self.semantic_weight * norm_score
            doc_map[result.document_id] = result

        for result in keyword_results:
            norm_score = result.score / max_keyword if max_keyword > 0 else 0
            combined_scores[result.document_id] += self.keyword_weight * norm_score
            if result.document_id not in doc_map:
                doc_map[result.document_id] = result

        sorted_ids = sorted(combined_scores.keys(), key=lambda x: combined_scores[x], reverse=True)

        results = []
        for doc_id in sorted_ids[:top_k]:
            result = doc_map[doc_id]
            result.score = combined_scores[doc_id]
            results.append(result)

        return results

    def _max_score_fusion(
        self,
        semantic_results: list[SearchResult],
        keyword_results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Take maximum score for each document across both searches."""
        max_scores: dict[str, float] = {}
        doc_map: dict[str, SearchResult] = {}

        for result in semantic_results:
            doc_id = result.document_id
            if doc_id not in max_scores or result.score > max_scores[doc_id]:
                max_scores[doc_id] = result.score
                doc_map[doc_id] = result

        for result in keyword_results:
            doc_id = result.document_id
            if doc_id not in max_scores or result.score > max_scores[doc_id]:
                max_scores[doc_id] = result.score
                doc_map[doc_id] = result

        sorted_ids = sorted(max_scores.keys(), key=lambda x: max_scores[x], reverse=True)

        return [doc_map[doc_id] for doc_id in sorted_ids[:top_k]]

    def _interleave_fusion(
        self,
        semantic_results: list[SearchResult],
        keyword_results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Interleave results from both searches."""
        results = []
        seen_ids = set()

        sem_iter = iter(semantic_results)
        key_iter = iter(keyword_results)
        use_semantic = True

        while len(results) < top_k:
            try:
                if use_semantic:
                    result = next(sem_iter)
                else:
                    result = next(key_iter)

                if result.document_id not in seen_ids:
                    results.append(result)
                    seen_ids.add(result.document_id)

                use_semantic = not use_semantic

            except StopIteration:
                # One iterator exhausted, drain the other
                for result in sem_iter:
                    if result.document_id not in seen_ids and len(results) < top_k:
                        results.append(result)
                        seen_ids.add(result.document_id)
                for result in key_iter:
                    if result.document_id not in seen_ids and len(results) < top_k:
                        results.append(result)
                        seen_ids.add(result.document_id)
                break

        return results

    def get_index_stats(self, collection: str = "default") -> dict[str, Any]:
        """Get statistics for a collection's keyword index."""
        index = self._collection_indexes.get(collection, self.bm25_index)

        return {
            "collection": collection,
            "total_documents": index.total_docs,
            "unique_terms": len(index.term_frequencies),
            "avg_document_length": index.avg_doc_length,
        }


class QueryExpander:
    """
    Query expansion for improving search recall.

    Techniques:
    - Synonym expansion
    - Acronym expansion
    - IoT/security domain expansion
    """

    def __init__(self):
        """Initialize query expander with domain-specific expansions."""
        self.synonyms = {
            "attack": ["exploit", "threat", "vulnerability", "compromise"],
            "security": ["protection", "defense", "safety"],
            "device": ["sensor", "actuator", "node", "endpoint"],
            "smart home": ["iot", "home automation", "connected home"],
            "botnet": ["malware network", "zombie network", "bot network"],
            "ddos": ["distributed denial of service", "flooding attack"],
            "intrusion": ["breach", "unauthorized access", "infiltration"],
        }

        self.acronyms = {
            "iot": "internet of things",
            "ids": "intrusion detection system",
            "ips": "intrusion prevention system",
            "ddos": "distributed denial of service",
            "mitm": "man in the middle",
            "ble": "bluetooth low energy",
            "mqtt": "message queuing telemetry transport",
            "coap": "constrained application protocol",
            "cve": "common vulnerabilities and exposures",
            "cwe": "common weakness enumeration",
            "mitre": "mitre att&ck framework",
        }

    def expand_query(
        self,
        query: str,
        max_expansions: int = 3,
    ) -> list[str]:
        """
        Expand a query with synonyms and acronyms.

        Args:
            query: Original query
            max_expansions: Maximum number of expanded queries to return

        Returns:
            List of expanded queries including original
        """
        expanded = [query]
        query_lower = query.lower()

        # Expand acronyms
        for acronym, expansion in self.acronyms.items():
            if acronym in query_lower:
                expanded_query = query_lower.replace(acronym, expansion)
                if expanded_query not in expanded:
                    expanded.append(expanded_query)

        # Expand synonyms
        for term, synonyms in self.synonyms.items():
            if term in query_lower:
                for syn in synonyms[:2]:  # Limit synonym expansion
                    expanded_query = query_lower.replace(term, syn)
                    if expanded_query not in expanded:
                        expanded.append(expanded_query)

        return expanded[:max_expansions + 1]


# Factory function
def get_hybrid_search(
    semantic_search_fn: Optional[Callable] = None,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4,
) -> HybridSearch:
    """Create a HybridSearch instance."""
    return HybridSearch(
        semantic_search_fn=semantic_search_fn,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
    )
