import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG-Bristol"
    API_V1_STR: str = "/api"
    
    # ChromaDB 配置
    CHROMA_PERSIST_DIRECTORY: str = os.getenv("CHROMA_DB_DIR", "./chroma_db")
    CHROMA_COLLECTION_NAME: str = "campus_notifications"
    
    # Redis 配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # 模型配置
    EMBEDDING_MODEL_NAME: str = "text-embedding-3-small"
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"
    LLM_MODEL_NAME: str = "gpt-4o"
    
    # OpenAI 配置
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://yunwu.ai/v1")
    
    class Config:
        env_file = ".env"

settings = Settings()
