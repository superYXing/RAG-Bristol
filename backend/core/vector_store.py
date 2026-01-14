import chromadb
from chromadb.config import Settings
import os
from pathlib import Path
from .config import settings
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

class VectorStore:
    def __init__(self):
        try:
            # 1. 初始化持久化客户端：数据将存储在指定的本地目录中
            Path(settings.CHROMA_PERSIST_DIRECTORY).mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY)
            self.collection_name = settings.CHROMA_COLLECTION_NAME
            
            device = "cuda"
            self.embedding_model = HuggingFaceBgeEmbeddings(
                model_name=settings.EMBEDDING_MODEL_NAME,
                model_kwargs={"device": device},
                encode_kwargs={"normalize_embeddings": True},
            )
            
            # 3. 确保数据表（Collection）存在
            self._ensure_collection()
        except Exception as e:
            # 容错处理：如果数据库连接失败，切换到 Mock 模式防止程序直接崩溃
            print(f"Failed to connect to ChromaDB: {e}")
            print("Running in MOCK mode for Vector Store.")
            self.client = None

    def _ensure_collection(self):
        """检查并获取指定的 Collection，如果不存在则自动创建"""
        if not self.client: return
        # get_or_create_collection 是 ChromaDB 的推荐做法
        # 显式指定使用 cosine 距离，以便计算相似度 score = 1 - distance
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"Collection {self.collection_name} ready.")

    def add_documents(self, chunks, batch_size=100):
        """
        将文档片段批量写入向量数据库
        chunks 格式要求: [{'content': '文本内容', 'metadata': {...}}, ...] 或 LangChain Document 对象
        """
        if not self.client:
            print(f"Mock Indexing {len(chunks)} chunks")
            return []
            
        total_chunks = len(chunks)
        all_ids = []
        
        print(f"Starting to index {total_chunks} chunks with batch size {batch_size}...")
        
        # 分批处理
        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i : i + batch_size]
            
            batch_data = []
            for c in batch_chunks:
                if isinstance(c, dict):
                    batch_data.append({
                        "content": c.get('content', ''),
                        "metadata": c.get('metadata', {})
                    })
                else:
                    batch_data.append({
                        "content": getattr(c, 'page_content', ''),
                        "metadata": getattr(c, 'metadata', {})
                    })

            import hashlib
            deduped = []
            seen_ids = set()
            for item in batch_data:
                content = item.get("content") or ""
                doc_id = hashlib.md5(content.encode()).hexdigest()
                if doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)
                deduped.append((doc_id, item))

            if not deduped:
                continue

            batch_ids = [doc_id for doc_id, _ in deduped]
            batch_documents = [item.get("content") or "" for _, item in deduped]
            
            try:
                batch_embeddings = self.embedding_model.embed_documents(batch_documents)
            except Exception as e:
                print(f"Embedding generation failed for batch {i}-{i+len(batch_chunks)}: {e}")
                continue
            
            batch_metadatas = []
            for _, item in deduped:
                meta = (item.get("metadata") or {}).copy()
                meta['date'] = str(meta.get('date', ''))
                for k, v in list(meta.items()):
                    if v is None:
                        meta[k] = ""
                        continue
                    if not isinstance(v, (str, int, float, bool)):
                        meta[k] = str(v)
                batch_metadatas.append(meta)
    
            # 执行数据库写入操作 (Batch)
            try:
                self.collection.upsert(
                    documents=batch_documents,
                    embeddings=batch_embeddings,
                    metadatas=batch_metadatas,
                    ids=batch_ids
                )
                all_ids.extend(batch_ids)
                print(f"Indexed batch {i // batch_size + 1}/{(total_chunks + batch_size - 1) // batch_size} ({len(batch_ids)} chunks).")
            except Exception as e:
                print(f"Error upserting batch to Chroma: {e}")

        print(f"Finished indexing. Total successful: {len(all_ids)}/{total_chunks}")
        return all_ids

    def search(self, query: str, limit: int = 10):
        """
        向量相似度搜索
        query: 用户的问题
        limit: 返回最相关的结果数量
        """
        if not self.client:
            print(f"Mock Search: {query}")
            return []
        
        # 1. 将用户的查询语句转化为向量（Query Embedding）
        try:
            dense_vec = self.embedding_model.embed_query(query)
        except Exception as e:
            print(f"Query embedding failed: {e}")
            return []
        
        # where_arg 可以用于后续扩展元数据过滤（例如：只查某一日期之后的通知）
        where_arg = None

        # 2. 在向量空间中搜索最接近的 Top-K 个结果
        results = self.collection.query(
            query_embeddings=[dense_vec],
            n_results=limit,
            where=where_arg,
            include=["documents", "metadatas", "distances"] # 指定返回的内容
        )
        
        # 3. 格式化返回结果：将 Chroma 原生格式转化为后端通用的字典格式
        hits = []
        if results['ids'] and len(results['ids']) > 0:
            # Chroma 返回的结果是嵌套列表 [[]]，所以需要取 [0]
            for i in range(len(results['ids'][0])):
                hits.append({
                    "id": results['ids'][0][i],
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "date": results['metadatas'][0][i].get("date"),
                    # 距离转化为相似度分数。Chroma 默认使用 L2 距离或余弦距离
                    # 相似度 = 1 - 距离（分数越高越相关）
                    "score": 1 - results['distances'][0][i] 
                })
        
        # 返回结果列表
        return hits # 建议改为直接返回 hits，而非 [hits]

# 实例化单例，供其他模块调用
vector_store = VectorStore()
