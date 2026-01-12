# Bristol Campus RAG System

本项目是一个检索增强生成（RAG）系统，旨在搜索和查询百万级校园通知。

## 特性

- **混合检索**：结合了稠密向量检索（BGE-M3）和稀疏向量检索（模拟 BM25），使用 ChromaDB。
- **重排序**：使用 BGE-Reranker 进行高精度的二阶段排序。
- **LLM 评审**：使用 GPT-4o-mini 验证检索文档的相关性。
- **元数据过滤**：支持按日期、源 URL 等进行过滤。
- **前后端分离**：
  - **后端**：FastAPI, ChromaDB, LangChain, Celery。
  - **前端**：React, Tailwind CSS, Lucide。

## 项目结构

```
RAG-Bristol/
├── backend/            # Python FastAPI 后端
│   ├── app.py          # API 入口点
│   ├── core/           # 核心逻辑
│   │   ├── config.py   # 设置
│   │   ├── ingest.py   # 数据处理
│   │   ├── vector_store.py # ChromaDB 集成
│   │   ├── retriever.py # 检索与重排
│   │   └── generator.py # LLM 生成
│   └── requirements.txt
├── frontend/           # React 前端
│   ├── src/
│   │   ├── App.tsx     # 主 UI
│   │   └── ...
└── data/               # 文档存储
```

## 安装与运行

### 先决条件
- Python 3.10+
- Node.js 18+
- OpenAI API Key

### 后端

1. 进入 `backend` 目录：
   ```bash
   cd backend
   ```
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 设置环境变量（创建 .env 或在 shell 中设置）：
   ```
   OPENAI_API_KEY=sk-...
   CHROMA_DB_DIR=./chroma_db # 可选，默认为 ./chroma_db
   ```
4. 运行服务器：
   ```bash
   python app.py
   ```

### 前端

1. 进入 `frontend` 目录：
   ```bash
   cd frontend
   ```
2. 安装依赖：
   ```bash
   npm install
   ```
3. 运行开发服务器：
   ```bash
   npm run dev
   ```

## API 使用

- **摄取 (Ingest)**：POST `/api/ingest` (上传 Markdown 文件)
- **搜索 (Search)**：POST `/api/search` `{"query": "..."}`
- **聊天 (Chat)**：POST `/api/chat` `{"query": "..."}`
