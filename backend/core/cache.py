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

    def lookup(self, query: str, scope: str = "chat", threshold: float = 0.99):
        """
        查找缓存。
        逻辑：
        1. 计算 Query 向量
        2. 在 ChromaDB 中搜索 Top 1 最相似的历史 Query (且 scope 匹配)
        3. 如果相似度 > threshold，则认为命中缓存
        4. 从 Redis 中取出对应的 Value
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
                where={"scope": scope},
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
                
                # 4. Fetch Value from Redis
                # Use scope in Redis key to avoid collisions if hash is same but scope differs (though ID in chroma is hash)
                # Wait, if ID is hash of query, and query is same, ID is same.
                # If we have same query for chat and search, we can't store both in Chroma with same ID but different metadata?
                # Chroma IDs must be unique.
                # So we must include scope in the ID/Hash.
                
                # RE-DESIGN:
                # If query="X", hash="H".
                # If we insert (H, scope="chat") and (H, scope="search"), Chroma will overwrite or fail if ID is same.
                # So ID must be hash(query + scope).
                
                # But wait, if I change the ID generation logic, I break the lookup logic unless lookup also generates ID same way.
                # BUT lookup searches by vector. It gets an ID back.
                # So if I insert with ID = hash(query + scope), lookup by vector will find it.
                # AND I should check Redis with that ID.
                
                cached_value = self.redis_client.get(f"cache:{cache_key}")
                if cached_value:
                    print(f"Cache HIT ({scope})! Similarity: {similarity:.4f}")
                    return cached_value
                else:
                    pass
            
            return None

        except Exception as e:
            print(f"Cache lookup failed: {e}")
            return None

    def update(self, query: str, value: str, scope: str = "chat"):
        """
        更新缓存。
        逻辑：
        1. 计算 Query + Scope Hash 作为 ID
        2. 存入 Redis (Key=ID, Value=Value)
        3. 计算 Query Vector 并存入 ChromaDB (Metadata include scope)
        """
        if not self.redis_available or not self.collection:
            return

        try:
            # 1. Generate ID (Include scope to allow same query for different scopes)
            query_hash = hashlib.md5((query + scope).encode()).hexdigest()
            
            # 2. Save to Redis (Set TTL to 24 hours)
            # Key uses the hash which already includes scope uniqueness
            self.redis_client.setex(f"cache:{query_hash}", 86400, value)
            
            # 3. Save to Vector DB
            query_vector = self.vector_store.embedding_model.embed_query(query)
            
            self.collection.upsert(
                ids=[query_hash],
                embeddings=[query_vector],
                metadatas=[{"original_query": query, "scope": scope}]
            )
            # print(f"Cache Updated for query: {query[:20]}... scope={scope}")

        except Exception as e:
            print(f"Cache update failed: {e}")

    def clear_all(self):
        deleted_redis = 0
        if self.redis_available:
            try:
                cursor = 0
                pattern = "cache:*"
                while True:
                    cursor, keys = self.redis_client.scan(cursor=cursor, match=pattern, count=500)
                    if keys:
                        deleted_redis += self.redis_client.delete(*keys)
                    if cursor == 0:
                        break
                print(f"SemanticCache: deleted {deleted_redis} Redis keys with prefix 'cache:'.")
            except Exception as e:
                print(f"SemanticCache: failed to clear Redis keys ({e}).")
        if self.collection and self.vector_store.client:
            try:
                self.vector_store.client.delete_collection(self.cache_collection_name)
                self.collection = None
                print(f"SemanticCache: deleted Chroma collection '{self.cache_collection_name}'.")
            except Exception as e:
                print(f"SemanticCache: failed to delete Chroma collection ({e}).")

semantic_cache = SemanticCache()
