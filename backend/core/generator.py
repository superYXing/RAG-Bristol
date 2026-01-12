from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .config import settings

class RAGGenerator:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            streaming=True,
            temperature=0.3
        )
        
        self.prompt = ChatPromptTemplate.from_template("""
你是一个布里斯托大学的校园客服助手。请根据以下参考资料回答用户问题。

---
参考资料：
{context}
---

用户问题：{query}

任务要求：
1. **整合与总结**：基于参考资料，回答用户的问题。如果资料不足，请诚实告知。
2. **多语言回复**：请识别用户问题的语言，并使用**相同的语言**进行回复。
3. **引用来源**：在回答中引用相关资料时，必须严格使用 `[编号]` 的格式（例如 `[1]`, `[2]`）。
4. **提供链接**：在回答的末尾，列出所有引用资料的官方链接（如果有）。

回答格式示例：
根据通知 [1]，考试将在...
...

参考链接：
[1] https://www.bristol.ac.uk/...
""")

    async def generate_stream(self, query: str, docs: list):
        if not docs:
            yield "未找到相关通知 (No relevant notifications found)."
            return

        # 格式化上下文
        context_parts = []
        for i, doc in enumerate(docs):
            title = doc['metadata'].get('title', '无标题')
            date = doc.get('date', '未知日期')
            url = doc['metadata'].get('url', '无链接')
            content = doc['content']
            context_parts.append(f"[{i+1}] 标题: {title} (日期: {date}, 链接: {url})\n内容: {content}\n")
        
        context_str = "\n".join(context_parts)
        
        chain = self.prompt | self.llm
        
        async for chunk in chain.astream({"query": query, "context": context_str}):
            yield chunk.content

rag_generator = RAGGenerator()
