# Bristol Campus RAG System

[🇨🇳 中文版](README.md)

This project is a Retrieval-Augmented Generation (RAG) system designed for fast retrieval and answer generation from the University of Bristol's campus notification documents. The system extracts information from massive Markdown documents and combines them with large language models to provide an intelligent campus assistant experience.

## Features

- **Interactive Experience**:
  - **Phased Visualization**: Real-time display of RAG pipeline stages (query rewriting, vector retrieval, reranking, generation) in Streamlit interface.
  - **Segmented Requests**: Retrieval triggers immediately after user query. The search API can efficiently and accurately match using BM25 keyword matching + vector retrieval within 1 second. Results are displayed immediately while summary generation continues (local LLM ~5s, API ~8s).
  - **Streaming Responses**: Model responses are streamed in real-time with a typewriter effect.
  - **Conversation History**: Locally persisted session records, displayed in a date-based tree structure in the sidebar, with one-click conversation restoration.
  - **Document Viewer**: Retrieved results support "View Full Text", displayed in a modal with one-click copy functionality.

- **Intelligent Retrieval**:
  - **Semantic Search**: Uses `BAAI/bge-small-en-v1.5` model to generate high-quality document vectors, retrieved via ChromaDB.
  - **Query Rewriting**: Uses `qwen2.5:7b` to optimize user queries and extract keywords.
  - **Cloud Reranking**: Integrates `BAAI/bge-reranker-v2-m3` for secondary precision ranking of initial retrieval results.

- **Performance Optimization**:
  - **Semantic Cache**: Introduces Redis + ChromaDB for two-tier caching mechanism.
  - **Concurrent Processing**: Frontend uses multi-threaded concurrent requests for responsive interface.
  - **Detailed Timing Statistics**: Provides precise timing data for each processing stage.

## System Architecture

The diagram below shows the overall architecture of the Bristol Campus RAG system, including frontend interaction layer, backend API service, retrieval pipeline (vector retrieval + BM25), and LLM generation module:

![RAG Bristol Architecture](asserts/rag_bristol_arichitecture.png)

## Tech Stack

- **Frontend**: Streamlit (Python), multi-stage progress indicators + document cards + conversation history
- **Backend**: FastAPI (Python)
- **Large Models**:
  - Rewriting / Generation: Qwen2.5:7b (default, shared local Ollama service), can be configured to switch to Gemini-3-Flash
  - Embedding: BAAI/bge-small-en-v1.5
  - Rerank: BAAI/bge-reranker-v2-m3 (local or API)
- **Databases**:
  - Vector Store: ChromaDB
  - Cache: Redis (semantic cache + BM25/vector hybrid retrieval)

## Project Structure

```
RAG-Bristol/
├── backend/            # Python FastAPI backend
│   ├── app.py          # API entry point
│   ├── core/           # Core business logic
│   │   ├── config.py   # Configuration management
│   │   ├── retriever.py # Retrieval and reranking logic
│   │   ├── generator.py # RAG generation logic
│   │   └── ...
│   └── ...
├── streamlit_app.py    # Streamlit frontend application
├── bristol_markdown/   # Raw Markdown document data
└── .env                # Environment variable configuration
```

## Performance Benchmark

Based on test data from 2026-01-15 (3-request average):

The diagram below shows the latency distribution of each stage when using the Qwen2.5:7b + BM25 hybrid retrieval scheme:

![Qwen + BM25 Latency Distribution](asserts/qwen+bm25_latency.png)

Key observations:
- **Vector Search** benefits from ChromaDB's efficient HNSW indexing, with latency around 100ms
- **Generate** stage takes the most time (~10 seconds), due to inherent latency of local LLM inference
- **Rerank** and **Rewrite** are the main optimization opportunities

## Data Format Examples

### Vector Database Storage Format (ChromaDB)

Documents are chunked and stored in ChromaDB with the following fields:

```json
{
  "id": "6f0b61e9bea65b7023c5f30f8bab504e",
  "document": "> During your time in Bristol we hope you'll discover why so many choose this city to live, work and study.\n\nUniversity residences, private rented accommodation, and chief and senior residents.\n\nStay active by signing up for a student membership or book sports classes online.",
  "metadata": {
    "title": "Life in Bristol",
    "url": "https://www.bristol.ac.uk/students/life-in-bristol/",
    "date": "2026-01-11",
    "description": "Information and advice about student life in Bristol.",
    "h2": "Student societies and volunteering"
  }
}
```

### Conversation History Format (chat_history.json)

Frontend conversation history is stored in JSON format at `.streamlit/chat_history.json`, supporting multi-turn dialogues and retrieval result records:

```json
{
  "id": "d9ce37288b3449cda1518e2b793815d0",
  "created_at": "2026-01-15T22:06:10",
  "updated_at": "2026-01-15T22:06:32",
  "title": "Where can I find the latest exam schedule?",
  "messages": [
    {
      "role": "assistant",
      "content": "Hello, I am the campus intelligent assistant. Please enter your question."
    },
    {
      "role": "user",
      "content": "Where can I find the latest exam schedule?"
    },
    {
      "role": "assistant",
      "content": "### Answer about exam schedule\nAccording to the latest campus notice **[3]**,...\n\n---\n### 🔗 References\n- [3] How to make an appeal [https://...]",
      "docs": [...],
      "sources": [...]
    }
  ]
}
```

## 🚀 Enterprise Architecture Optimization Roadmap

### 1. Overall Architecture Evolution

The current architecture is a typical **"monolith + microservice prototype"** with the following bottlenecks:

| Bottleneck Type | Current Status |
|----------------|----------------|
| 🔴 Single Point of Failure | API Server and ChromaDB are both single instances |
| 🔴 Synchronous Blocking | LLM calls and Rerank compute-intensive tasks may block the main thread |
| 🔴 Connection Pool Limits | Database and Redis connections may be exhausted under high concurrency |

**Target Architecture**: Cloud-native distributed architecture based on **Kubernetes (K8s)**.

---

### 2. Core Layer Optimization

#### Layer 1: Access Layer & Gateway

**Current State**: Streamlit directly calls FastAPI, lacking traffic control.

**Optimization Directions**:

| Item | Implementation |
|------|---------------|
| **Load Balancing** | Introduce Nginx or cloud ALB/SLB before API for traffic distribution and SSL offloading |
| **API Gateway** | Introduce Kong or APISIX |
| **Rate Limiting** | Rate limit by tenant or IP to prevent attacks or resource exhaustion |
| **Authentication** | Unified JWT authentication to reduce backend pressure |
| **Frontend-Backend Separation** | Deprecate Streamlit in production (prototype only), use React/Vue with static assets on CDN, backend provides REST/GraphQL only |

---

#### Layer 2: Application Layer

**Current State**: Single-machine FastAPI, mixed compute and I/O.

**Optimization Directions**:

##### Stateless Horizontal Scaling
- Containerize FastAPI service (Docker)
- Use K8s HPA (Horizontal Pod Autoscaler) to auto-scale based on CPU/memory usage

##### Full Async Transformation
- Use Python `asyncio` for all IO-intensive operations (DB reads/writes, LLM requests)
- Use **Server-Sent Events (SSE)** or **WebSocket** instead of HTTP streaming for stable long connections

##### Compute Separation
- **Rerank Model as Microservice**: Reranking (FlagReranker) is compute-intensive (GPU/CPU), should be separated as independent microservice
- Recommended: Deploy with **Triton Inference Server** or **TorchServe** for independent scaling

---

#### Layer 3: Data & Storage Layer

**Current State**: ChromaDB single instance, Redis mixed usage.

**Optimization Directions**:

##### Vector Database Clustering
| Solution | Description |
|----------|-------------|
| Distributed Chroma | Migrate to Chroma's distributed deployment mode (Client-Server mode) |
| Alternatives | Migrate to **Milvus Cluster** or **Qdrant** with sharding and replication support |
| Read-Write Separation | Read replicas for high-frequency retrieval, primary node for writes (Upsert) |

##### Redis High Availability
| Solution | Description |
|----------|-------------|
| Cluster Deployment | Deploy **Redis Cluster** or **Sentinel** mode for cache and queue HA |
| Protection Strategy | Implement **Bloom Filter** and random expiration for cache penetration/avalanche prevention |

---

#### Layer 4: LLM Model Gateway Layer

**Current State**: Direct external API calls, single vendor dependency.

**Optimization Directions**:

##### Model Routing & Circuit Breaking
- Build unified model gateway (e.g., **LiteLLM**)
- **Multi-vendor Rotation**: Auto-fallback to Azure OpenAI, Anthropic, or local Qwen/Llama when OpenAI has high latency or errors
- **Smart Retry (Exponential Backoff)**: Implement exponential backoff for 429 (Rate Limit) errors

##### Enhanced Semantic Cache
- Improve Semantic Cache hit rate
- Return cached results directly for high similarity queries (> 0.95), bypassing LLM entirely
- 🎯 **Expected Impact**: QPS can increase **10-100x**, the most effective way to improve concurrency
