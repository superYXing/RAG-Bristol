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
import math
from typing import List, Dict, Any

# Add current directory to path so imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import settings
from core.retriever import rag_retriever
from core.generator import rag_generator
from core.cache import semantic_cache
from core.vector_store import vector_store
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("rag")
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, "rag_debug.jsonl")
file_handler_exists = False
for h in logger.handlers:
    if isinstance(h, logging.FileHandler):
        try:
            if getattr(h, "baseFilename", None) == os.path.abspath(log_path):
                file_handler_exists = True
                break
        except Exception:
            continue
if not file_handler_exists:
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)

chat_router_llm = ChatOpenAI(
    model=settings.REWRITE_MODEL_NAME,
    api_key=settings.REWRITE_API_KEY,
    base_url=settings.REWRITE_BASE_URL,
    temperature=0.3,
)

chat_router_prompt = ChatPromptTemplate.from_template("""
You are a Conversation Routing Assistant responsible for determining whether a user's question requires accessing the University of Bristol Campus Notification Knowledge Base (RAG) for an answer.
Classification Rules
Classify a question as "requires RAG Knowledge Base query" if it falls into any of these categories:
Asks for information, policies, procedures, dates, locations, or services related to the University of Bristol
Asks about university courses, programs, degrees, applications, registration, exams, grades, tuition, scholarships, etc.
Asks about official information on university libraries, accommodation, student support, visas, immigration, campus life, etc.
Explicitly seeks answers based on "official materials", "notifications", "university website", or "school regulations"

If it is casual conversation or does not rely on specific campus notifications, such as:
Greetings or functional questions like "Who are you?", "Hello", "What can you do?"
Questions about the weather, jokes, casual chat, or life advice
General questions unrelated to the University of Bristol,
then just respond as a normal chat assitant.

Output Rules
If the question requires RAG Knowledge Base query:
Output only: YES,Do not add any other content, symbols, or explanations.
If the question is not required to be answered by the RAG Knowledge Base, do NOT respond with 'No' or any simple negative words. Instead, directly answer the user's question in a concise, friendly and positive tone, acting as the University of Bristol Campus Chat Assistant.
User question: {query}
""")

chat_router_chain = chat_router_prompt | chat_router_llm | StrOutputParser()


def sanitize_floats(obj: Any) -> Any:
    """
    Recursively sanitize float values in a data structure to ensure JSON compatibility.
    Replaces inf, -inf, and nan with 0.0.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    elif isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_floats(item) for item in obj]
    return obj


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
        results = await asyncio.to_thread(vector_store.search, rewritten_query, 15)
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
                # Sanitize floats to avoid JSON serialization errors
                return {"results": sanitize_floats(cached_docs), "latency_ms": elapsed_ms, "from_cache": True}
        except Exception as e:
            logger.error(f"Cache parse failed: {e}")

    docs = await rag_retriever.retrieve(req.query, request_id=request_id)
    
    # Sanitize floats before caching and returning
    docs = sanitize_floats(docs)
    
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
    try:
        routed = await chat_router_chain.ainvoke({"query": req.query})
        text = str(routed or "").strip()
    except Exception as e:
        logger.info(json.dumps({"event": "api_chat_route_error", "request_id": request_id, "error": str(e)}, ensure_ascii=False))
        text = ""
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    if text.upper() == "YES":
        logger.info(json.dumps({"event": "api_chat_decision", "request_id": request_id, "mode": "rag", "ms": elapsed_ms}, ensure_ascii=False))
        return {"decision": "search"}
    answer = text or "抱歉，我暂时无法理解你的问题。"
    logger.info(json.dumps({"event": "api_chat_decision", "request_id": request_id, "mode": "chat", "ms": elapsed_ms}, ensure_ascii=False))
    return {"decision": "answer", "answer": answer}

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
