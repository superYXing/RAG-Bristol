from celery import Celery
from .config import settings
from .ingest import processor
import os

# Initialize Celery
celery_app = Celery("rag_worker", broker=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery_app.task(name="process_and_index_doc")
def process_and_index_doc(file_path: str):
    """
    Async task to process a markdown file and index it into Milvus.
    """
    if not os.path.exists(file_path):
        return f"File not found: {file_path}"

    # 1. Process document
    chunks = processor.process_file(file_path)
    
    if not chunks:
        return f"No chunks generated from {file_path}"

    # 2. Index into Vector Store
    try:
        from .vector_store import vector_store
        vector_store.add_documents(chunks)
    except Exception as e:
        return f"Error indexing {file_path}: {str(e)}"
    
    return f"Processed and indexed {len(chunks)} chunks from {file_path}"
