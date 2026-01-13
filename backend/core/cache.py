import json
import hashlib
import redis
from .config import settings
from .vector_store import vector_store

class SemanticCache:
    def __init__(self):
        # 1. 初始化 Redis 连接
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            # 测试连接
            self.redis_client.ping()
            self.redis_available = True
            print("SemanticCache: Redis connected successfully.")
        except Exception as e:
            print(f"SemanticCache: Redis connection failed ({e}). Cache will be disabled.")
            self.redis_available = False

        # 2. 初始化 ChromaDB Cache Collection
        # 我们使用 ChromaDB 来存储 Query 的向量索引，以实现“语义极其相似”的查找
        self.cache_collection_name = "semantic_query_cache"
        self.vector_store = vector_store
        
        if self.vector_store.client:
            self.collection = self.vector_store.client.get_or_create_collection(
                name=self.cache_collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        else:
            self.collection = None

    def lookup(self, query: str, threshold: float = 0.95):
        """
        查找缓存。
        逻辑：
        1. 计算 Query 向量
        2. 在 ChromaDB 中搜索 Top 1 最相似的历史 Query
        3. 如果相似度 > threshold，则认为命中缓存
        4. 从 Redis 中取出对应的 Answer
        """
        if not self.redis_available or not self.collection:
            return None

        try:
            # 1. Embed Query
            query_vector = self.vector_store.embedding_model.embed_query(query)

            # 2. Search Vector DB
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=1,
                include=["metadatas", "distances"]
            )

            if not results['ids'] or len(results['ids'][0]) == 0:
                return None

            # 3. Check Similarity
            # Cosine Distance: 0 (Identical) -> 2 (Opposite)
            # Similarity = 1 - Distance
            distance = results['distances'][0][0]
            similarity = 1 - distance
            
            # print(f"Cache Lookup: Best match similarity = {similarity:.4f}")

            if similarity >= threshold:
                cache_key = results['ids'][0][0] # ID is the hash of the original query
                
                # 4. Fetch Answer from Redis
                cached_answer = self.redis_client.get(f"cache:{cache_key}")
                if cached_answer:
                    print(f"Cache HIT! Similarity: {similarity:.4f}")
                    return cached_answer
                else:
                    # Inconsistency: Vector exists but Redis data missing (expired?)
                    # Clean up vector? For now just ignore.
                    pass
            
            return None

        except Exception as e:
            print(f"Cache lookup failed: {e}")
            return None

    def update(self, query: str, answer: str):
        """
        更新缓存。
        逻辑：
        1. 计算 Query Hash 作为 ID
        2. 存入 Redis (Key=Hash, Value=Answer)
        3. 计算 Query Vector 并存入 ChromaDB
        """
        if not self.redis_available or not self.collection:
            return

        try:
            # 1. Generate ID
            query_hash = hashlib.md5(query.encode()).hexdigest()
            
            # 2. Save to Redis (Set TTL to 24 hours, for example)
            self.redis_client.setex(f"cache:{query_hash}", 86400, answer)
            
            # 3. Save to Vector DB
            # We need to embed again (inefficient but safe). 
            # Optimization: pass vector from lookup if possible, but for now keep simple.
            query_vector = self.vector_store.embedding_model.embed_query(query)
            
            self.collection.upsert(
                ids=[query_hash],
                embeddings=[query_vector],
                metadatas=[{"original_query": query}]
            )
            # print(f"Cache Updated for query: {query[:20]}...")

        except Exception as e:
            print(f"Cache update failed: {e}")

semantic_cache = SemanticCache()
