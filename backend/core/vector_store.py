import chromadb
from chromadb.config import Settings
import os
from .config import settings
from langchain_openai import OpenAIEmbeddings

class VectorStore:
    def __init__(self):
        try:
            self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY)
            self.collection_name = settings.CHROMA_COLLECTION_NAME
            
            # 初始化 OpenAI Embeddings
            self.embedding_model = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL_NAME,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL
            )
            
            self._ensure_collection()
        except Exception as e:
            print(f"Failed to connect to ChromaDB: {e}")
            print("Running in MOCK mode for Vector Store.")
            self.client = None

    def _ensure_collection(self):
        if not self.client: return
        # Chroma automatically gets or creates
        self.collection = self.client.get_or_create_collection(name=self.collection_name)
        print(f"Collection {self.collection_name} ready.")

    def add_documents(self, chunks):
        if not self.client:
            print(f"Mock Indexing {len(chunks)} chunks")
            return []
            
        texts = [c['content'] for c in chunks]
        
        # 生成 Embeddings (使用 OpenAI API)
        try:
            embeddings = self.embedding_model.embed_documents(texts)
        except Exception as e:
            print(f"Embedding generation failed: {e}")
            return []
        
        ids = []
        metadatas = []
        documents = []

        for i, chunk in enumerate(chunks):
            # Chroma 需要 string ID
            # 我们生成一个简单的 ID，或者使用 content hash
            import hashlib
            doc_id = hashlib.md5(chunk['content'].encode()).hexdigest()
            
            ids.append(doc_id)
            documents.append(chunk['content'])
            
            # Metadata 处理
            meta = chunk['metadata'].copy()
            meta['date'] = str(meta.get('date', ''))
            # Chroma metadata values must be int, float, str, bool
            # Ensure all are str if unsure
            for k, v in meta.items():
                if not isinstance(v, (str, int, float, bool)):
                    meta[k] = str(v)
            metadatas.append(meta)

        # 批量写入
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Inserted {len(documents)} documents into ChromaDB.")
        return ids

    def search(self, query: str, limit: int = 10):
        if not self.client:
            print(f"Mock Search: {query}")
            return []
        
        # 1. Encode Query
        try:
            dense_vec = self.embedding_model.embed_query(query)
        except Exception as e:
            print(f"Query embedding failed: {e}")
            return []
        
        # 2. Build Filter (Removed date filter logic as requested previously, or keep generic empty)
        # Note: Previous instruction removed date filter from Retriever, but VectorStore still had the method signature.
        # We should align with the new requirement. The user removed date args from Retriever.
        # Let's keep it simple.
        where_arg = None

        # 3. Search
        results = self.collection.query(
            query_embeddings=[dense_vec],
            n_results=limit,
            where=where_arg,
            include=["documents", "metadatas", "distances"]
        )
        
        # Convert to Unified Format for Retriever
        hits = []
        if results['ids'] and len(results['ids']) > 0:
            for i in range(len(results['ids'][0])):
                hits.append({
                    "id": results['ids'][0][i],
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "date": results['metadatas'][0][i].get("date"),
                    # Chroma returns distance. Similarity = 1 - distance (approx for cosine/l2 normalized)
                    "score": 1 - results['distances'][0][i] 
                })
        
        return [hits]

vector_store = VectorStore()
