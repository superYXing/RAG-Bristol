from celery import Celery
from .config import settings
from .ingest import processor
import os

# 1. 初始化 Celery 实例
# "rag_worker" 是当前 Worker 的名称
# broker 是消息中间件（Redis），用于接收和存放任务队列
celery_app = Celery("rag_worker", broker=settings.REDIS_URL)
app = celery_app

# 2. Celery 配置更新
celery_app.conf.update(
    task_serializer='json',      # 任务数据（参数）序列化格式
    accept_content=['json'],     # 允许接收的内容类型
    result_serializer='json',    # 任务结果序列化格式
    timezone='UTC',              # 设置时区
    enable_utc=True,             # 开启 UTC
)

# 3. 定义异步任务
# @celery_app.task 装饰器将普通函数转变为可由 Worker 执行的任务
# name 参数方便在其他地方（如 FastAPI）通过名称调用该任务
@celery_app.task(name="process_and_index_doc")
def process_and_index_doc(file_path: str):
    """
    异步任务：处理 Markdown 文件并将其索引至向量数据库（Chroma/Milvus）。
    参数 file_path: 待处理文件的绝对路径
    """
    
    # 基础安全性检查：确保文件路径在磁盘上真实存在
    if not os.path.exists(file_path):
        return f"File not found: {file_path}"

    # --- 步骤 1: 文档处理 ---
    # 调用 processor 模块解析 Markdown 内容、提取元数据并切片 (Chunking)
    chunks = processor.process_file(file_path)
    
    # 如果文件是空的或解析失败，直接返回
    if not chunks:
        return f"No chunks generated from {file_path}"

    # --- 步骤 2: 向量化与入库 ---
    try:
        # 在任务内部导入 vector_store 避免循环依赖 (Circular Import)
        from .vector_store import vector_store
        
        # 将切片后的数据送入向量数据库，此过程包含：
        # 1. 调用 Embedding 模型接口
        # 2. 写入数据库磁盘
        vector_store.add_documents(chunks)
        
    except Exception as e:
        # 捕获入库过程中的所有异常（如数据库连接断开、API 欠费等）
        return f"Error indexing {file_path}: {str(e)}"
    
    # 返回执行结果，该结果会被存入 Redis (如果配置了 Result Backend)
    return f"Processed and indexed {len(chunks)} chunks from {file_path}"
