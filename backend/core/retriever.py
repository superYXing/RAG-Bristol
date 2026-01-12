from .vector_store import vector_store
from .config import settings
import requests

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

class RAGRetriever:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            temperature=0
        )

    def retrieve(self, query: str):
        # 0. 查询重写/翻译
        rewritten_query = self._rewrite_query(query)
        print(f"原查询: {query} -> 重写后: {rewritten_query}")

        # 1. 混合检索 (召回 50 条)
        try:
            results = vector_store.search(rewritten_query, limit=50)
        except Exception as e:
            print(f"检索失败: {e}")
            return []
        
        candidates = []
        # Milvus/Chroma 结果是 Hits 列表。results[0] 对应第一个查询向量。
        if results and len(results) > 0:
            for hit in results[0]: 
                # 确保获取内容。如果不在 output_fields 中，Milvus 可能不会返回。
                candidates.append({
                    "content": hit.get("content"),
                    "metadata": hit.get("metadata"),
                    "date": hit.get("date"),
                    "score": hit.get("score"),
                    "id": hit.get("id")
                })
        
        if not candidates:
            return []

        # 2. 重排序 (Rerank via API)
        try:
            doc_texts = [c['content'] for c in candidates]
            scores = self._rerank_api(rewritten_query, doc_texts)
            
            for i, score in enumerate(scores):
                candidates[i]['rerank_score'] = score
            
            # 按重排序分数排序
            candidates.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
            
        except Exception as e:
            print(f"重排序失败，使用原始排序: {e}")
            # 如果重排序失败，回退到原始向量分数排序 (已经默认排好，或者不需要操作)
        
        # 取前 5
        top_k = candidates[:5]
        
        # 3. LLM 评审 (Judge)
        # 使用原查询进行评审，确保相关性符合用户原始意图
        judged_results = self._judge_relevance(query, top_k)
        
        return judged_results

    def _rerank_api(self, query: str, documents: list) -> list:
        # 假设 Rerank API 位于 OPENAI_BASE_URL/rerank (例如 https://yunwu.ai/v1/rerank)
        url = f"{settings.OPENAI_BASE_URL}/rerank"
        # 移除可能的双斜杠 (如果 BASE_URL 以 / 结尾)
        if settings.OPENAI_BASE_URL.endswith('/'):
            url = f"{settings.OPENAI_BASE_URL}rerank"
            
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.RERANKER_MODEL_NAME,
            "query": query,
            "documents": documents,
            "top_n": len(documents) 
        }
        
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise Exception(f"API Error {resp.status_code}: {resp.text}")
            
        data = resp.json()
        results = data.get('results', [])
        
        # 映射回原始顺序
        # API 通常返回 [{"index": 0, "relevance_score": 0.9}, ...]
        final_scores = [0.0] * len(documents)
        for res in results:
            idx = res.get('index')
            score = res.get('relevance_score')
            if idx is not None and idx < len(final_scores):
                final_scores[idx] = score
                
        return final_scores

    def _rewrite_query(self, query: str) -> str:
        prompt = PromptTemplate.from_template("""
        你是一个助手，负责将用户的查询转换为用于检索英文校园通知的关键词。
        
        用户查询: {query}
        
        请执行以下操作：
        1. 理解用户的意图。
        2. 将查询翻译成英文（如果不是英文）。
        3. 提取核心关键词。
        4. 输出仅包含关键词的字符串，用空格分隔。
        
        输出:
        """)
        try:
            chain = prompt | self.llm | StrOutputParser()
            rewritten = chain.invoke({"query": query})
            return rewritten.strip()
        except Exception as e:
            print(f"查询重写失败: {e}")
            return query

    def _judge_relevance(self, query, docs):
        if not docs:
            return []
            
        # 使用前 200 个字符进行快速判断
        context_str = "\n".join([f"[{i+1}] {d['content'][:200]}..." for i, d in enumerate(docs)])
        
        prompt = PromptTemplate.from_template("""
        你是一个相关性评审员。
        查询: {query}
        文档:
        {context}
        
        这些文档中是否有包含回答查询所需的相关信息？
        请严格回复 'YES' 或 'NO'。
        """)
        
        try:
            chain = prompt | self.llm | StrOutputParser()
            judgment = chain.invoke({"query": query, "context": context_str})
            print(f"LLM 评审结果: {judgment}")
            
            if "YES" in judgment.strip().upper():
                return docs
            else:
                return []
        except Exception as e:
            print(f"LLM 评审失败: {e}")
            return docs # 如果评审失败，回退到返回原文档

rag_retriever = RAGRetriever()
