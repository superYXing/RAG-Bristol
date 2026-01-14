# Bristol Campus RAG System

本项目是一个检索增强生成（RAG）系统，旨在从布里斯托大学的校园通知文档中进行快速检索并生成回答。系统支持从海量 Markdown 文档中提取信息，结合大模型提供智能客服体验。

目前已升级为 **Streamlit** 前端，提供更加流畅的流式对话和分阶段处理可视化体验。

## 特性

- **交互式体验**：
  - **分阶段可视化**：在 Streamlit 界面实时展示 RAG 管道的各个阶段（查询改写、向量检索、重排序、生成）。
  - **分段请求**：用户提问后立即触发检索，检索结果返回后立即展示并继续生成总结。
  - **流式回答**：生成模型的回复以打字机效果实时流式输出。
  - **历史会话**：本地持久化保存会话记录，并在侧边栏以日期树状结构折叠展示，可一键恢复对话。
  - **文档查看**：检索结果支持“查看全文”，以模态框展示完整内容并支持一键复制。

- **智能检索**：
  - **语义搜索**：使用 `BAAI/bge-small-en-v1.5` 模型生成高质量文档向量，通过 ChromaDB 进行检索。
  - **查询改写**：使用 `qwen2.5:7b` 对用户查询进行优化和关键词提取。
  - **云端重排序**：集成 `BAAI/bge-reranker-v2-m3` 对初步检索结果进行二次精排，提升相关性。

- **性能优化**：
  - **语义缓存**：引入 Redis + ChromaDB 构建二级缓存机制。
  - **并发处理**：前端采用多线程并发请求，确保界面响应迅速。
  - **详细耗时统计**：提供每个处理阶段的精确耗时数据。

## 技术栈

- **前端**：Streamlit (Python)
- **后端**：FastAPI (Python)
- **大模型**：
  - 生成: Gemini-3-Flash-Preview
  - 改写: Qwen2.5:7b
  - Embedding: BAAI/bge-small-en-v1.5
  - Rerank: BAAI/bge-reranker-v2-m3
- **数据库**：
  - 向量库: ChromaDB
  - 缓存: Redis

## 项目结构

```
RAG-Bristol/
├── backend/            # Python FastAPI 后端
│   ├── app.py          # API 入口点
│   ├── core/           # 核心业务逻辑
│   │   ├── config.py   # 配置管理
│   │   ├── retriever.py # 检索与重排序逻辑
│   │   ├── generator.py # RAG 生成逻辑
│   │   └── ...
│   └── ...
├── streamlit_app.py    # Streamlit 前端应用
├── bristol_markdown/   # 原始 Markdown 文档数据
└── .env                # 环境变量配置文件
```

## 安装与运行

### 1. 环境准备
- Python 3.10+
- Redis 服务
- Conda (推荐)

### 2. 后端启动
1. 确保 Redis 服务已运行。
2. 配置 `.env` 文件（参考 `.env.example` 或直接创建）：
   ```properties
   OPENAI_API_KEY=your_key
   OPENAI_BASE_URL=https://yunwu.ai/v1
   REDIS_URL=redis://localhost:6379/0
   CHROMA_DB_DIR=backend/chroma_db
   ```
3. 运行 FastAPI 后端：
   ```bash
   python backend/app.py
   ```
   后端将在 `http://localhost:8000` 启动。

### 3. 前端启动
新开一个终端窗口，运行 Streamlit 应用：
```bash
streamlit run streamlit_app.py
```
应用将在浏览器中自动打开（默认地址 `http://localhost:8502`，可在 `.streamlit/config.toml` 修改）。

> 注意：不要使用 `python streamlit_app.py` 直接运行。

### 4. 本地历史会话存储
前端会将历史会话写入本地文件：
- `.streamlit/chat_history.json`

## RAG 流程图

![alt text](image.png)

## 性能基准测试 (Benchmark)

基于 2026-01-13 的测试数据 (3次请求平均值)：

| 阶段 (Stage) | 平均耗时 (Mean) | P50 (ms) | P95 (ms) | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **Query Rewrite** | 859.16 ms | 880.66 | 885.38 | 使用本地 Qwen2.5:7b 模型 |
| **Vector Search** | 64.33 ms | 40.89 | 105.48 | ChromaDB 检索 |
| **Rerank** | 3965.72 ms | 3865.03 | 4147.89 | BAAI/bge-reranker-v2-m3 (API) |
| **TTFT** | 7400.09 ms | 7480.41 | 7674.47 | 首字生成时间 (含改写+检索+重排) |
| **Generate** | 9101.95 ms | 8946.80 | 9525.95 | Gemini-3-Flash 生成完整回复 |
| **Total E2E** | 13991.26 ms | 14119.53 | 14276.16 | 端到端总耗时 |

> **注意**: Rerank 阶段目前通过外部 API 调用，耗时较高 (~4s)，是主要的性能瓶颈之一。TTFT 包含了从请求开始到生成第一个字符的所有前置步骤。
