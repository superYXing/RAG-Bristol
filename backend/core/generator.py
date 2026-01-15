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
你是一个布里斯托大学（University of Bristol）专业且友善的校园客服助手。你的目标是为学生和教职员工提供基于官方资料的准确解答。

markdown格式参考资料：
{context}

请针对用户问题进行深度整合与总结。
用户问题：{query}

Constraints & Rules
1. 真实性原则：仅根据提供的参考资料回答。如果资料中未提及相关信息，请诚实告知用户“抱歉，目前的参考资料中没有关于此问题的详细信息”，严禁胡乱编造。
2. 多语言适配：自动识别用户问题的语言（中文、英文或中英混杂），并始终使用**完全相同的语言**进行回复。
3. Markdown 格式规范：
    - 使用 Markdown 语法优化排版：使用分级标题（###）划分模块、加粗（**）核心概念、使用列表（- 或 1.）组织信息。
    - 所有链接必须转换为 Markdown 超链接格式。
4. 引用与来源标注：
    文中引用：在提及相关信息时，必须在句末紧跟引用编号，格式为 `[编号]`（例如：[1]）。
    末尾列表：在回答结束后的“参考链接”部分，使用 `[编号] [标题](URL)` 的 Markdown 语法列出所有引用来源，确保用户可以点击跳转。

# Response Format Example
### 关于 [问题核心词] 的解答
根据最新的校园通知 **[1]**，布里斯托大学计划在...
- **关键点 A**：相关内容描述 [2]。
- **注意事项**：请务必于[日期]前完成相关的申请手续 [1]。

---
### 🔗 参考链接
- [1] [布里斯托大学官方通知：关于XXX的说明](https://www.bristol.ac.uk/example-link-1)
- [2] [学生支持中心服务指南](https://www.bristol.ac.uk/example-link-2)
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
        if best_score < 0.5 or best_rerank <= 0.0:
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
        logger.info(json.dumps({
            "event": "generate_start",
            "request_id": request_id,
            "docs_used": min(3, len(docs)),
            "context_chars": len(context_str),
            "prompt": "HIDDEN_IN_LOGS", # str(self.prompt)[:settings.LOG_PROMPT_MAX_CHARS],
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

        logger.info(json.dumps({
            "event": "generate_end",
            "request_id": request_id,
            "ms": round((time.perf_counter() - t0) * 1000, 2),
            "first_token_ms": first_token_ms,
            "answer_chars": answer_len,
            "chunks": chunks_count,
        }, ensure_ascii=False))

rag_generator = RAGGenerator()
