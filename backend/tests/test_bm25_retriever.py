"""
test_bm25_retriever.py - BM25 Keyword Retrieval Unit Tests

This module tests the BM25 (Best Matching 25) keyword-based retrieval
functionality integrated with the hybrid retrieval system:
- BM25 score computation for document ranking
- Hybrid weighting between keyword and vector scores
- Token caching for performance optimization

Run with:
    python -m pytest test_bm25_retriever.py -v
"""

import unittest
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.retriever import RAGRetriever, BM25Scorer  # type: ignore


class TestBM25Retriever(unittest.TestCase):
    def setUp(self) -> None:
        self.retriever = RAGRetriever()

    def test_bm25_scores_prefer_matching_document(self) -> None:
        candidates = [
            {"id": "1", "content": "the cat sat on the mat", "score": 0.2},
            {"id": "2", "content": "the dog sat on the log", "score": 0.8},
        ]
        scores = self.retriever._compute_bm25_scores("cat mat", candidates)
        self.assertEqual(len(scores), 2)
        self.assertGreater(scores[0], scores[1])

    def test_hybrid_weighting_respects_keyword_weight(self) -> None:
        candidates = [
            {"id": "1", "content": "cat mat", "score": 0.1, "rerank_score": 0.1},
            {"id": "2", "content": "dog log", "score": 0.9, "rerank_score": 0.9},
        ]
        self.retriever._kw_weight = 0.9
        self.retriever._vec_weight = 0.1
        bm25_scores = self.retriever._compute_bm25_scores("cat mat", candidates)
        for i, s in enumerate(bm25_scores):
            candidates[i]["bm25_score"] = s
        self.retriever._apply_hybrid_scores(candidates)
        self.assertGreater(candidates[0]["hybrid_score"], candidates[1]["hybrid_score"])

    def test_token_cache_reused(self) -> None:
        candidates = [
            {"id": "1", "content": "exam schedule and timetable", "score": 0.5},
            {"id": "2", "content": "library opening hours", "score": 0.5},
        ]
        self.retriever._bm25_token_cache.clear()
        self.retriever._compute_bm25_scores("exam", candidates)
        initial_cache_size = len(self.retriever._bm25_token_cache)
        self.retriever._compute_bm25_scores("timetable", candidates)
        self.assertEqual(initial_cache_size, len(self.retriever._bm25_token_cache))


if __name__ == "__main__":
    unittest.main()

