from .vector_store import vector_store
from .config import settings
import asyncio
import json
import logging
import os
import time
import math
import re
from typing import Any, Dict, List

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
try:
    from FlagEmbedding import FlagReranker
except Exception:
    FlagReranker = None

logger = logging.getLogger("rag")


class BM25Scorer:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = float(k1)
        self.b = float(b)

    def tokenize(self, text: str) -> List[str]:
        tokens = re.findall(r"\w+", text.lower())
        return tokens

    def score(self, query_tokens: List[str], documents_tokens: List[List[str]]) -> List[float]:
        if not documents_tokens:
            return []
        N = len(documents_tokens)
        doc_freqs: Dict[str, int] = {}
        doc_lens: List[int] = []
        for doc in documents_tokens:
            doc_lens.append(len(doc))
            unique_terms = set(doc)
            for term in unique_terms:
                doc_freqs[term] = doc_freqs.get(term, 0) + 1
        avgdl = sum(doc_lens) / float(N)
        idf: Dict[str, float] = {}
        for term, df in doc_freqs.items():
            idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
        scores: List[float] = []
        q_terms = list(dict.fromkeys(query_tokens))
        for idx, doc in enumerate(documents_tokens):
            score_val = 0.0
            if not doc:
                scores.append(0.0)
                continue
            dl = doc_lens[idx]
            freqs: Dict[str, int] = {}
            for t in doc:
                freqs[t] = freqs.get(t, 0) + 1
            for term in q_terms:
                freq = freqs.get(term, 0)
                if freq == 0:
                    continue
                term_idf = idf.get(term, 0.0)
                denom = freq + self.k1 * (1.0 - self.b + self.b * dl / avgdl)
                score_val += term_idf * (freq * (self.k1 + 1.0) / denom)
            scores.append(score_val)
        return scores


class RAGRetriever:
    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=settings.REWRITE_MODEL_NAME,
            api_key=settings.REWRITE_API_KEY,
            base_url=settings.REWRITE_BASE_URL,
            temperature=0
        )
        self.reranker = None
        if FlagReranker is not None:
            self.reranker = FlagReranker(
                settings.RERANKER_MODEL_NAME,
                use_fp16=True,
                devices="cuda"
            )
        kw_weight = max(float(getattr(settings, "BM25_KEYWORD_WEIGHT", 0.4)), 0.0)
        vec_weight = max(float(getattr(settings, "BM25_VECTOR_WEIGHT", 0.6)), 0.0)
        if kw_weight == 0.0 and vec_weight == 0.0:
            kw_weight, vec_weight = 0.4, 0.6
        total = kw_weight + vec_weight
        self._kw_weight = kw_weight / total
        self._vec_weight = vec_weight / total
        self._bm25_enabled = bool(getattr(settings, "BM25_ENABLED", True))
        self._bm25 = BM25Scorer()
        self._bm25_token_cache: Dict[str, List[str]] = {}

    async def retrieve(self, query: str, request_id: str = "") -> List[Dict[str, Any]]:
        t0 = time.perf_counter()
        timing_stats = {"rewrite": 0, "vector_search": 0, "rerank": 0, "total": 0}
        
        logger.info(json.dumps({"event": "retrieve_start", "request_id": request_id, "query": query}, ensure_ascii=False))

        rewritten_query, rewrite_debug = await self._rewrite_query(query)
        timing_stats["rewrite"] = rewrite_debug["ms"]
        

        try:
            t_search = time.perf_counter()
            results = await asyncio.to_thread(vector_store.search, rewritten_query, 20)
            search_ms = round((time.perf_counter() - t_search) * 1000, 2)
            timing_stats["vector_search"] = search_ms
        except Exception as e:
            logger.info(json.dumps({"event": "vector_search_error", "request_id": request_id, "error": str(e)}, ensure_ascii=False))
            return []
        
        candidates = []
        if results and len(results) > 0:
            for hit in results: 
                candidates.append({
                    "content": hit.get("content"),
                    "metadata": hit.get("metadata"),
                    "date": hit.get("date"),
                    "score": hit.get("score"),
                    "id": hit.get("id")
                })

        if not candidates:
            timing_stats["total"] = round((time.perf_counter() - t0) * 1000, 2)
            return []

        top1_similarity = float(candidates[0].get("score") or 0.0)
        top5_preview = []
        for c in candidates[:5]:
            meta = c.get("metadata") or {}
            # content = (c.get("content") or "") # Removed to reduce log noise
            top5_preview.append({
                "id": c.get("id"),
                "score": c.get("score"),
                "title": meta.get("title"),
                "url": meta.get("url"),
                # "content_preview": content[:settings.LOG_TEXT_MAX_CHARS], # Removed
            })

        try:
            doc_texts = [c["content"] for c in candidates]
            t_rerank = time.perf_counter()
            scores = await self._rerank(rewritten_query, doc_texts)
            rerank_ms = round((time.perf_counter() - t_rerank) * 1000, 2)
            timing_stats["rerank"] = rerank_ms
            for i, score in enumerate(scores):
                candidates[i]["rerank_score"] = score
            candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        except Exception as e:
            logger.info(json.dumps({"event": "rerank_error", "request_id": request_id, "error": str(e)}, ensure_ascii=False))

        if self._bm25_enabled:
            bm25_scores = self._compute_bm25_scores(rewritten_query, candidates)
            for i, s in enumerate(bm25_scores):
                candidates[i]["bm25_score"] = s
            self._apply_hybrid_scores(candidates)

        top_k = candidates[:5]
        
        timing_stats["total"] = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(json.dumps({
            "event": "retrieve_end", 
            "request_id": request_id, 
            "ms": timing_stats["total"], 
            "docs": len(top_k),
            "latency_breakdown": timing_stats
        }, ensure_ascii=False))
        return top_k

    async def _rerank(self, query: str, documents: List[str]) -> List[float]:
        mode = (getattr(settings, "RERANK_MODE", "") or "api").lower()
        if mode == "api":
            return await self._rerank_api(query, documents)
        return await self._rerank_local(query, documents)

    async def _rerank_api(self, query: str, documents: List[str]) -> List[float]:
        if not documents:
            return []
        base_url = settings.RERANK_BASE_URL.rstrip("/")
        api_key = settings.RERANK_API_KEY
        if not api_key:
            raise RuntimeError("RERANK_API_KEY is required for RERANK_MODE=api")

        url = f"{base_url}/rerank"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        top_n = min(10, len(documents))
        payload = {
            "model": settings.RERANKER_MODEL_NAME,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=3.0)) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        if isinstance(data, dict):
            if isinstance(data.get("results"), list):
                results = data.get("results") or []
            elif isinstance(data.get("data"), list):
                results = data.get("data") or []

        final_scores = [0.0] * len(documents)
        for res in results:
            if not isinstance(res, dict):
                continue
            idx = res.get("index")
            score = res.get("relevance_score")
            if score is None:
                score = res.get("score")
            if isinstance(idx, int) and 0 <= idx < len(final_scores):
                try:
                    final_scores[idx] = float(score)
                except Exception:
                    final_scores[idx] = 0.0
        return final_scores

    async def _rerank_local(self, query: str, documents: List[str]) -> List[float]:
        if self.reranker is None:
            return [0.0] * len(documents)
        top_n = min(10, len(documents))
        pairs = [[query, doc] for doc in documents[:top_n]]
        scores = await asyncio.to_thread(self.reranker.compute_score, pairs)
        final_scores = [0.0] * len(documents)
        for i, s in enumerate(scores):
            final_scores[i] = float(s)
        return final_scores

    def _compute_bm25_scores(self, query: str, candidates: List[Dict[str, Any]]) -> List[float]:
        query_tokens = self._bm25.tokenize(query)
        docs_tokens: List[List[str]] = []
        for c in candidates:
            doc_id = str(c.get("id") or "")
            content = str(c.get("content") or "")
            if doc_id in self._bm25_token_cache:
                tokens = self._bm25_token_cache[doc_id]
            else:
                tokens = self._bm25.tokenize(content)
                if doc_id:
                    self._bm25_token_cache[doc_id] = tokens
            docs_tokens.append(tokens)
        return self._bm25.score(query_tokens, docs_tokens)

    def _apply_hybrid_scores(self, candidates: List[Dict[str, Any]]) -> None:
        if not candidates:
            return
        bm25_vals: List[float] = []
        vec_vals: List[float] = []
        for c in candidates:
            bm25_vals.append(float(c.get("bm25_score") or 0.0))
            vec = c.get("rerank_score")
            if vec is None:
                vec = c.get("score") or 0.0
            vec_vals.append(float(vec))
        bm25_norm = self._normalize_scores(bm25_vals)
        vec_norm = self._normalize_scores(vec_vals)
        for i, c in enumerate(candidates):
            hybrid = bm25_norm[i] * self._kw_weight + vec_norm[i] * self._vec_weight
            c["hybrid_score"] = hybrid
        candidates.sort(key=lambda x: x.get("hybrid_score", x.get("rerank_score", 0.0)), reverse=True)

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        if not scores:
            return []
        min_v = min(scores)
        max_v = max(scores)
        if max_v == min_v:
            return [0.0 for _ in scores]
        scale = max_v - min_v
        return [(s - min_v) / scale for s in scores]

    async def _rewrite_query(self, query: str):
        prompt = PromptTemplate.from_template("""
        你是一个助手，负责将用户的查询转换为用于检索英文校园通知的关键词,站在校园事务查询的立场上进行适当的关键词扩写。
        
        用户查询: {query}
        
        请执行以下操作：
        1. 理解用户的意图。
        2. 将查询翻译成英文（如果不是英文）,回答只包含英文。
        3. 提取核心关键词
        4. 输出仅包含关键词的字符串，用空格分隔。
        
        示例： 用户输入：“如何办理退学”
        输出：“withdrawal application, withdrawal procedure, school leaving process, campus administration student enrollment office”
        """)
        try:
            chain = prompt | self.llm | StrOutputParser()
            t = time.perf_counter()
            rewritten = await chain.ainvoke({"query": query})
            ms = round((time.perf_counter() - t) * 1000, 2)
            return rewritten.strip(), {
                "ms": ms,
                "prompt": (prompt.template or "")[:settings.LOG_PROMPT_MAX_CHARS],
                "input": {"query": query},
                "output": rewritten.strip()[:settings.LOG_TEXT_MAX_CHARS],
            }
        except Exception as e:
            return query, {
                "ms": 0,
                "prompt": (prompt.template or "")[:settings.LOG_PROMPT_MAX_CHARS],
                "input": {"query": query},
                "output": query[:settings.LOG_TEXT_MAX_CHARS],
                "error": str(e),
            }

rag_retriever = RAGRetriever()
