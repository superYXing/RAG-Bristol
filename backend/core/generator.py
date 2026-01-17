import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .config import settings
import logging
import time

logger = logging.getLogger("rag")

class RAGGenerator:
    def __init__(self):
        provider = (getattr(settings, "GENERATE_PROVIDER", "") or "qwen").lower()
        if provider == "qwen":
            model = settings.REWRITE_MODEL_NAME
            api_key = settings.REWRITE_API_KEY
            base_url = settings.REWRITE_BASE_URL
        elif provider == "gemini":
            model = getattr(settings, "GEMINI_MODEL_NAME", settings.GENERATE_MODEL_NAME)
            api_key = settings.GENERATE_API_KEY or settings.OPENAI_API_KEY or None
            base_url = settings.GENERATE_BASE_URL
        else:
            model = settings.GENERATE_MODEL_NAME
            api_key = settings.GENERATE_API_KEY or settings.OPENAI_API_KEY or None
            base_url = settings.GENERATE_BASE_URL

        self.llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            streaming=True,
            temperature=0.3
        )
        
        self.prompt = ChatPromptTemplate.from_template("""
# Role
Role & Objective
You are a professional and friendly campus customer service assistant for the University of Bristol. Your goal is to provide accurate, official-source-based answers to students, faculty, and staff.

Input Format
Markdown reference materials:
{context}

Please conduct in-depth integration and summarization in response to the user's question.
User question: {query}

Constraints & Rules
Authenticity Principle: Only answer based on the provided reference materials. If the relevant information is not mentioned in the materials, honestly inform the user: "Sorry, there is no detailed information about this question in the current reference materials." Do not fabricate content.
Markdown Formatting Standards:
Use Markdown syntax for better readability: Use level-3 headings (###) to separate sections, bold for core concepts, and bullet points (- or 1.) to organize information.
All links must be converted to Markdown hyperlink format.

""")

    async def generate_stream(self, query: str, docs: list, request_id: str = "", cache_update_callback=None):
        t0 = time.perf_counter()
        if not docs:
            yield "未找到相关通知 (No relevant notifications found)."
            logger.info(json.dumps({"event": "generate_empty", "request_id": request_id, "ms": round((time.perf_counter() - t0) * 1000, 2)}, ensure_ascii=False))
            return

        scores = [float((d.get("score") or 0.0)) for d in docs]
        reranks = [float((d.get("rerank_score") or 0.0)) for d in docs]
        best_score = max(scores) if scores else 0.0
        best_rerank = max(reranks) if reranks else 0.0
        if best_score < 0.6 and best_rerank <= 0.0:
            yield "未找到相关通知 (No relevant notifications found)."
            logger.info(json.dumps({
                "event": "generate_low_confidence",
                "request_id": request_id,
                "ms": round((time.perf_counter() - t0) * 1000, 2),
                "best_score": best_score,
                "best_rerank": best_rerank,
            }, ensure_ascii=False))
            return

        top_docs = []
        for i, doc in enumerate(docs[:3]):
            top_docs.append({
                "id": i + 1,
                "content": doc.get('content', ''),
                "metadata": doc.get('metadata', {}),
                "score": doc.get('rerank_score') or doc.get('score'),
                "date": doc.get('date')
            })
        
        source_msg = f"__SOURCES__:{json.dumps(top_docs)}\n"
        yield source_msg

        context_parts = []
        for i, doc in enumerate(docs[:3]):
            title = doc['metadata'].get('title', '无标题')
            date = doc.get('date', '未知日期')
            url = doc['metadata'].get('url', '无链接')
            content = doc['content']
            context_parts.append(f"[{i+1}] 标题: {title} (日期: {date}, 链接: {url})\n内容: {content}\n")
        
        context_str = "\n".join(context_parts)
        try:
            messages = self.prompt.format_messages(query=query, context=context_str)
            prompt_text = "\n\n".join([getattr(m, "content", "") for m in messages])
        except Exception:
            prompt_text = ""
        logger.info(json.dumps({
            "event": "generate_start",
            "request_id": request_id,
            "docs_used": min(3, len(docs)),
            "context_chars": len(context_str),
            "prompt": prompt_text[: settings.LOG_PROMPT_MAX_CHARS] if prompt_text else "",
        }, ensure_ascii=False))
        
        chain = self.prompt | self.llm
        
        cache_parts = [source_msg]
        answer_len = 0
        first_token_ms = None
        chunks_count = 0

        async for chunk in chain.astream({"query": query, "context": context_str}):
            piece = chunk.content or ""
            if first_token_ms is None:
                first_token_ms = round((time.perf_counter() - t0) * 1000, 2)
            yield piece
            cache_parts.append(piece)
            answer_len += len(piece)
            chunks_count += 1
        
        total_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(json.dumps({
            "event": "generate_end",
            "request_id": request_id,
            "ms": total_ms,
            "ttft": first_token_ms, # Time To First Token
            "chunks": chunks_count,
            "char_count": answer_len
        }, ensure_ascii=False))
            
        if cache_update_callback:
            try:
                if answer_len > 10:
                    cache_update_callback("".join(cache_parts))
            except Exception as e:
                logger.info(json.dumps({"event": "cache_update_error", "request_id": request_id, "error": str(e)}, ensure_ascii=False))


rag_generator = RAGGenerator()
