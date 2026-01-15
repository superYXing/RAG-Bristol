from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import json
import time
import uuid
import os
import sys
import asyncio
from typing import List, Dict, Any

# Add current directory to path so imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import settings
from core.retriever import rag_retriever
from core.generator import rag_generator
from core.cache import semantic_cache
from core.vector_store import vector_store

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("rag")

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    query: str

class ChatRequest(BaseModel):
    query: str

class SummarizeRequest(BaseModel):
    query: str
    docs: List[Dict[str, Any]]

@app.post("/api/pipeline")
async def pipeline(req: SearchRequest):
    request_id = uuid.uuid4().hex
    t0 = time.perf_counter()

    timing_ms = {"rewrite": 0.0, "vector_search": 0.0, "rerank": 0.0, "total": 0.0}

    rewritten_query, rewrite_debug = await rag_retriever._rewrite_query(req.query)
    timing_ms["rewrite"] = float(rewrite_debug.get("ms") or 0.0)

    t_search = time.perf_counter()
    try:
        results = await asyncio.to_thread(vector_store.search, rewritten_query, 20)
    except Exception as e:
        timing_ms["vector_search"] = round((time.perf_counter() - t_search) * 1000, 2)
        timing_ms["total"] = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "request_id": request_id,
            "query": req.query,
            "rewritten_query": rewritten_query,
            "timing_ms": timing_ms,
            "error": str(e),
            "vector_hits": [],
            "top_k": [],
        }
    timing_ms["vector_search"] = round((time.perf_counter() - t_search) * 1000, 2)

    candidates = []
    if results and len(results) > 0:
        for hit in results:
            candidates.append(
                {
                    "content": hit.get("content"),
                    "metadata": hit.get("metadata"),
                    "date": hit.get("date"),
                    "score": hit.get("score"),
                    "id": hit.get("id"),
                }
            )

    if candidates:
        t_rerank = time.perf_counter()
        try:
            doc_texts = [(c.get("content") or "") for c in candidates]
            scores = await rag_retriever._rerank(rewritten_query, doc_texts)
            for i, score in enumerate(scores):
                candidates[i]["rerank_score"] = score
            candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        except Exception:
            pass
        timing_ms["rerank"] = round((time.perf_counter() - t_rerank) * 1000, 2)

    top_k = candidates[:5]
    vector_hits_preview = []
    for c in candidates[:10]:
        meta = c.get("metadata") or {}
        content = c.get("content") or ""
        vector_hits_preview.append(
            {
                "id": c.get("id"),
                "score": c.get("score"),
                "rerank_score": c.get("rerank_score"),
                "title": meta.get("title"),
                "url": meta.get("url"),
                "date": c.get("date"),
                "content_preview": content[:400],
            }
        )

    timing_ms["total"] = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "request_id": request_id,
        "query": req.query,
        "rewritten_query": rewritten_query,
        "timing_ms": timing_ms,
        "vector_hits": vector_hits_preview,
        "top_k": top_k,
    }

@app.post("/api/search")
async def search(req: SearchRequest):
    request_id = uuid.uuid4().hex
    t0 = time.perf_counter()
    logger.info(json.dumps({"event": "api_search_start", "request_id": request_id, "query": req.query}, ensure_ascii=False))
    
    # Cache Lookup
    cached_docs_str = semantic_cache.lookup(req.query, scope="search")
    if cached_docs_str:
        try:
            cached_docs = json.loads(cached_docs_str)
            if isinstance(cached_docs, list):
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                logger.info(json.dumps({"event": "api_search_cache_hit", "request_id": request_id, "ms": elapsed_ms}, ensure_ascii=False))
                return {"results": cached_docs, "latency_ms": elapsed_ms, "from_cache": True}
        except Exception as e:
            logger.error(f"Cache parse failed: {e}")

    docs = await rag_retriever.retrieve(req.query, request_id=request_id)
    
    # Update Cache
    try:
        semantic_cache.update(req.query, json.dumps(docs, ensure_ascii=False), scope="search")
    except Exception as e:
        logger.error(f"Cache update failed: {e}")

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info(json.dumps({"event": "api_search_end", "request_id": request_id, "ms": elapsed_ms, "results": len(docs)}, ensure_ascii=False))
    return {"results": docs, "latency_ms": elapsed_ms, "from_cache": False}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    request_id = uuid.uuid4().hex
    t0 = time.perf_counter()
    logger.info(json.dumps({"event": "api_chat_start", "request_id": request_id, "query": req.query}, ensure_ascii=False))
    cached_answer = semantic_cache.lookup(req.query)
    if cached_answer:
        logger.info(json.dumps({"event": "api_chat_cache_hit", "request_id": request_id, "ms": round((time.perf_counter() - t0) * 1000, 2)}, ensure_ascii=False))
        async def cached_stream():
            if isinstance(cached_answer, str) and cached_answer.startswith("__SOURCES__:"):
                head, sep, tail = cached_answer.partition("\n")
                yield head + "\n"
                if tail:
                    yield tail
                return
            yield cached_answer
        return StreamingResponse(
            cached_stream(),
            media_type="text/event-stream"
        )

    docs = await rag_retriever.retrieve(req.query, request_id=request_id)
    logger.info(json.dumps({"event": "api_chat_retrieved", "request_id": request_id, "ms": round((time.perf_counter() - t0) * 1000, 2), "docs": len(docs)}, ensure_ascii=False))
    
    return StreamingResponse(
        rag_generator.generate_stream(req.query, docs, request_id=request_id, cache_update_callback=lambda ans: semantic_cache.update(req.query, ans)),
        media_type="text/event-stream"
    )

@app.post("/api/summarize")
async def summarize(req: SummarizeRequest):
    request_id = uuid.uuid4().hex
    logger.info(json.dumps({"event": "api_summarize_start", "request_id": request_id, "query": req.query, "docs_count": len(req.docs)}, ensure_ascii=False))
    
    return StreamingResponse(
        rag_generator.generate_stream(req.query, req.docs, request_id=request_id),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
