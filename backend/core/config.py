import os
from pathlib import Path
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG-Bristol"
    API_V1_STR: str = "/api"
    
    # ChromaDB 配置
    CHROMA_PERSIST_DIRECTORY: str = str(PROJECT_ROOT / "backend" / "chroma_db")
    CHROMA_COLLECTION_NAME: str = "campus_notifications"
    
    # Redis 配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # 模型配置
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"
    LLM_MODEL_NAME: str = "qwen2.5:7b"

    RERANK_MODE: str = "local"
    RERANK_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    RERANK_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://yunwu.ai/v1")
    
    # OpenAI 配置
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://yunwu.ai/v1")

    REWRITE_API_KEY: str = "ollama"
    REWRITE_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    REWRITE_MODEL_NAME: str = "qwen2.5:7b"

    # 生成模型配置
    # GENERATE_PROVIDER:
    #   - "qwen": 复用改写模型（本地 Qwen，通过 LLM_BASE_URL / REWRITE_* 配置）
    #   - "gemini": 使用 OpenAI 兼容服务（通过 OPENAI_* / GEMINI_* 配置）
    #   - 其他值: 回退到 GENERATE_* 显式配置
    GENERATE_PROVIDER: str = "qwen"

    GENERATE_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GENERATE_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://yunwu.ai/v1")
    GENERATE_MODEL_NAME: str = "qwen2.5:7b"

    GEMINI_MODEL_NAME: str = "gemini-3-flash-preview"
    
    BM25_ENABLED: bool = True
    BM25_KEYWORD_WEIGHT: float = 0.4
    BM25_VECTOR_WEIGHT: float = 0.6
    
    LOG_LEVEL: str = "INFO"
    LOG_PROMPT_MAX_CHARS: int = 12000
    LOG_TEXT_MAX_CHARS: int = 400
    
    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        extra = "ignore"

settings = Settings()
