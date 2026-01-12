from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import shutil
import os
import sys

# Add current directory to path so imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.config import settings
from core.tasks import process_and_index_doc
from core.retriever import rag_retriever
from core.generator import rag_generator

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    query: str
    date_start: Optional[str] = None
    date_end: Optional[str] = None

class ChatRequest(BaseModel):
    query: str
    date_start: Optional[str] = None
    date_end: Optional[str] = None

@app.post("/api/ingest")
async def ingest_files(files: List[UploadFile] = File(...)):
    # 保存文件到 data/ 并触发任务
    results = []
    # 确保 data 目录存在
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    for file in files:
        file_path = os.path.join(data_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 触发处理 (为了演示简单起见使用同步方式)
        try:
            res = process_and_index_doc(file_path)
            results.append({"filename": file.filename, "status": "success", "msg": str(res)})
        except Exception as e:
            results.append({"filename": file.filename, "status": "error", "msg": str(e)})
    
    return {"message": "摄取已处理", "details": results}

@app.post("/api/search")
async def search(req: SearchRequest):
    docs = rag_retriever.retrieve(req.query)
    return {"results": docs}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    # 1. 检索
    docs = rag_retriever.retrieve(req.query)
    
    # 2. 生成流
    # 注意: 如果 docs 为空，生成器会处理。
    
    return StreamingResponse(
        rag_generator.generate_stream(req.query, docs),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
