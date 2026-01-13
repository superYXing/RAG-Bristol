import os
from pathlib import Path
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG-Bristol"
    API_V1_STR: str = "/api"
    
    # ChromaDB 配置
    CHROMA_PERSIST_DIRECTORY: str = os.getenv("CHROMA_DB_DIR") or str(PROJECT_ROOT / "backend" / "chroma_db")
    CHROMA_COLLECTION_NAME: str = "campus_notifications"
    
    # Redis 配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # 模型配置
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"
    LLM_MODEL_NAME: str = "qwen2.5:7b"

    RERANK_MODE: str = os.getenv("RERANK_MODE", "api")
    RERANK_API_KEY: str = os.getenv("RERANK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAPI_KEY") or ""
    RERANK_BASE_URL: str = os.getenv("RERANK_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://yunwu.ai/v1")
    
    # OpenAI 配置
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAPI_KEY") or ""
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://yunwu.ai/v1")

    REWRITE_API_KEY: str = os.getenv("REWRITE_API_KEY", "ollama")
    REWRITE_BASE_URL: str = os.getenv("REWRITE_BASE_URL", os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"))
    REWRITE_MODEL_NAME: str = os.getenv("REWRITE_MODEL_NAME", "qwen2.5:7b")

    GENERATE_API_KEY: str = os.getenv("GENERATE_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAPI_KEY") or ""
    GENERATE_BASE_URL: str = os.getenv("GENERATE_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://yunwu.ai/v1"))
    GENERATE_MODEL_NAME: str = os.getenv("GENERATE_MODEL_NAME", "gemini-3-flash-preview")
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_PROMPT_MAX_CHARS: int = int(os.getenv("LOG_PROMPT_MAX_CHARS", "12000"))
    LOG_TEXT_MAX_CHARS: int = int(os.getenv("LOG_TEXT_MAX_CHARS", "400"))
    
    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        extra = "ignore"

settings = Settings()
