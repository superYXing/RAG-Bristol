from .vector_store import vector_store
from .config import settings
import asyncio
import json
import logging
import os
import time

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
try:
    from FlagEmbedding import FlagReranker
except Exception:
    FlagReranker = None

logger = logging.getLogger("rag")

class RAGRetriever:
    def __init__(self):
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
                use_fp16=os.getenv("RERANKER_FP16", "1") not in ("0", "false", "False"),
                devices=os.getenv("RERANKER_DEVICES") or None
            )

    async def retrieve(self, query: str, request_id: str = ""):
        t0 = time.perf_counter()
        timing_stats = {"rewrite": 0, "vector_search": 0, "rerank": 0, "total": 0}
        
        logger.info(json.dumps({"event": "retrieve_start", "request_id": request_id, "query": query}, ensure_ascii=False))

        rewritten_query, rewrite_debug = await self._rewrite_query(query)
        timing_stats["rewrite"] = rewrite_debug["ms"]
        
        logger.info(json.dumps({
            "event": "rewrite_done",
            "request_id": request_id,
            "ms": rewrite_debug["ms"],
            "prompt": rewrite_debug["prompt"],
            "input": rewrite_debug["input"],
            "output": rewrite_debug["output"],
        }, ensure_ascii=False))

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
            logger.info(json.dumps({
                "event": "vector_search_empty", 
                "request_id": request_id, 
                "ms": search_ms,
                "latency_breakdown": timing_stats
            }, ensure_ascii=False))
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
        logger.info(json.dumps({
            "event": "vector_search_done",
            "request_id": request_id,
            "ms": search_ms,
            "rewritten_query": rewritten_query,
            "hits": len(candidates),
            "top1_similarity": top1_similarity,
            "top5": top5_preview,
        }, ensure_ascii=False))

        try:
            doc_texts = [c['content'] for c in candidates]
            t_rerank = time.perf_counter()
            scores = await self._rerank(rewritten_query, doc_texts)
            rerank_ms = round((time.perf_counter() - t_rerank) * 1000, 2)
            timing_stats["rerank"] = rerank_ms
            
            for i, score in enumerate(scores):
                candidates[i]['rerank_score'] = score
            
            candidates.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
            logger.info(json.dumps({
                "event": "rerank_done",
                "request_id": request_id,
                "ms": rerank_ms,
                "top_n": min(10, len(doc_texts)),
                "top5": [
                    {
                        "id": c.get("id"),
                        "rerank_score": c.get("rerank_score"),
                        "score": c.get("score"),
                        "title": (c.get("metadata") or {}).get("title"),
                        "url": (c.get("metadata") or {}).get("url"),
                    }
                    for c in candidates[:5]
                ],
            }, ensure_ascii=False))
            
        except Exception as e:
            logger.info(json.dumps({"event": "rerank_error", "request_id": request_id, "error": str(e)}, ensure_ascii=False))
        
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

    async def _rerank(self, query: str, documents: list) -> list:
        mode = (getattr(settings, "RERANK_MODE", "") or "api").lower()
        if mode == "api":
            return await self._rerank_api(query, documents)
        return await self._rerank_local(query, documents)

    async def _rerank_api(self, query: str, documents: list) -> list:
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

    async def _rerank_local(self, query: str, documents: list) -> list:
        if self.reranker is None:
            return [0.0] * len(documents)
        top_n = min(10, len(documents))
        pairs = [[query, doc] for doc in documents[:top_n]]
        scores = await asyncio.to_thread(self.reranker.compute_score, pairs)
        final_scores = [0.0] * len(documents)
        for i, s in enumerate(scores):
            final_scores[i] = float(s)
        return final_scores

    async def _rewrite_query(self, query: str):
        prompt = PromptTemplate.from_template("""
        你是一个助手，负责将用户的查询转换为用于检索英文校园通知的关键词,站在校园事务查询的立场上进行适当的关键词扩写。
        
        用户查询: {query}
        
        请执行以下操作：
        1. 理解用户的意图。
        2. 将查询翻译成英文（如果不是英文）。
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
